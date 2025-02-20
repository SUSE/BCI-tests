#!/usr/bin/env python3
import enum
import os
from datetime import timedelta
from pathlib import Path
from typing import Iterable
from typing import Optional
from typing import Sequence
from typing import Tuple

from pytest_container import DerivedContainer
from pytest_container.container import ContainerVolume
from pytest_container.container import PortForwarding
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import LOCALHOST

try:
    from typing import Literal
except ImportError:
    # typing.Literal is available on python3.8+
    # https://docs.python.org/3/library/typing.html#typing.Literal
    from typing_extensions import Literal

import pytest
from _pytest.mark.structures import MarkDecorator
from _pytest.mark.structures import ParameterSet

from bci_tester.runtime_choice import DOCKER_SELECTED

#: The operating system version as present in /etc/os-release & various other
#: places
OS_VERSION = os.getenv("OS_VERSION", "15.6")

# Allowed os versions for base (non lang/non-app) containers
ALLOWED_BASE_OS_VERSIONS = (
    "15.3",
    "15.4",
    "15.5",
    "15.6",
    "15.7",
    "16.0",
    "tumbleweed",
)

# Allowed os versions for Language and Application containers
ALLOWED_NONBASE_OS_VERSIONS = (
    "15.6",
    "15.6-ai",
    "15.7",
    "16.0",
    "tumbleweed",
)

# Allowed os versions for SLE_BCI repo checks
ALLOWED_BCI_REPO_OS_VERSIONS = (
    "15.6",
    "15.6-ai",
    "15.7",
    "tumbleweed",
)

# Test Language and Application containers by default for these versions
_DEFAULT_NONBASE_SLE_VERSIONS = ("15.6", "15.7")

# Test Language and Application containers by default for these versions
_DEFAULT_NONBASE_OS_VERSIONS = ("15.6", "15.7", "tumbleweed")

# Test base containers by default for these versions
_DEFAULT_BASE_OS_VERSIONS = ("15.6", "15.7", "16.0", "tumbleweed")

# List the released versions of SLE, used for supportabilty and EULA tests
RELEASED_SLE_VERSIONS = ("15.3", "15.4", "15.5", "15.6", "15.6-ai")

assert sorted(ALLOWED_BASE_OS_VERSIONS) == list(ALLOWED_BASE_OS_VERSIONS), (
    f"list ALLOWED_BASE_OS_VERSIONS must be sorted, but got {ALLOWED_BASE_OS_VERSIONS}"
)

assert sorted(ALLOWED_NONBASE_OS_VERSIONS) == list(
    ALLOWED_NONBASE_OS_VERSIONS
), (
    f"list ALLOWED_NONOS_VERSIONS must be sorted, but got {ALLOWED_NONBASE_OS_VERSIONS}"
)

if not (
    OS_VERSION in ALLOWED_BASE_OS_VERSIONS
    or OS_VERSION in ALLOWED_NONBASE_OS_VERSIONS
):
    raise ValueError(
        f"Invalid OS_VERSION: {OS_VERSION}, allowed values are: "
        + ", ".join(
            set(ALLOWED_BASE_OS_VERSIONS).union(
                set(ALLOWED_NONBASE_OS_VERSIONS)
            )
        )
    )


if OS_VERSION == "tumbleweed":
    OS_MAJOR_VERSION = 17
    OS_SP_VERSION = 0
    OS_CONTAINER_TAG = "latest"
    APP_CONTAINER_PREFIX = SAC_CONTAINER_PREFIX = "opensuse"
    BCI_CONTAINER_PREFIX = "bci"
    OS_VERSION_ID = None

    #: The Tumbleweed pretty name (from /etc/os-release)
    OS_PRETTY_NAME = os.getenv(
        "OS_PRETTY_NAME",
        "openSUSE Tumbleweed",
    )
else:
    APP_CONTAINER_PREFIX = "suse"
    SAC_CONTAINER_PREFIX = "containers"
    BCI_CONTAINER_PREFIX = "bci"
    OS_CONTAINER_TAG = OS_VERSION
    OS_VERSION_ID = OS_VERSION.partition("-")[0]

    OS_MAJOR_VERSION, OS_SP_VERSION = (
        int(ver) for ver in OS_VERSION_ID.split(".")
    )

    #: The SLES 15 pretty name (from /etc/os-release)
    OS_PRETTY_NAME = os.getenv(
        "OS_PRETTY_NAME",
        (
            f"SUSE Linux Enterprise Server {OS_MAJOR_VERSION} SP{OS_SP_VERSION}"
            if OS_MAJOR_VERSION == 15
            else f"SUSE Linux Enterprise Server {OS_MAJOR_VERSION}.{OS_SP_VERSION}"
        ),
    )

    assert OS_MAJOR_VERSION in (15, 16), (
        "The tests are created for SLE 15 base images only, "
        f"but got a request for SLE {OS_MAJOR_VERSION}"
    )


#: value of the environment variable ``TARGET`` which defines whether we are
#: taking the images from OBS, IBS or the ``CR:ToTest`` project on IBS
TARGET = os.getenv("TARGET", "obs")

#: If no target is defined, then you have to supply your own registry BASEURL
#: via this variable instead
BASEURL = os.getenv("BASEURL")

if TARGET not in (
    "obs",
    "ibs",
    "ibs-cr",
    "dso",
    "factory-totest",
    "factory-arm-totest",
    "ibs-released",
):
    if BASEURL is None:
        raise ValueError(
            f"Unknown target {TARGET} specified and BASEURL is not set, cannot continue"
        )
    if BASEURL.endswith("/"):
        BASEURL = BASEURL[:-1]
else:
    if OS_VERSION in ("tumbleweed", "16.0"):
        DISTNAME = OS_VERSION
    else:
        DISTNAME = f"sle-{OS_MAJOR_VERSION}-sp{OS_SP_VERSION}"

    ibs_cr_project: str = f"registry.suse.de/suse/{DISTNAME}/update/cr/totest"
    if OS_VERSION.startswith("16"):
        ibs_cr_project = (
            f"registry.suse.de/suse/slfo/products/sles/{DISTNAME}/test"
        )
    if OS_VERSION == "15.6-ai":
        ibs_cr_project = (
            "registry.suse.de/suse/sle-15-sp6/update/products/ai/totest"
        )

    BASEURL = {
        "obs": f"registry.opensuse.org/devel/bci/{DISTNAME}",
        "factory-totest": "registry.opensuse.org/opensuse/factory/totest",
        "factory-arm-totest": "registry.opensuse.org/opensuse/factory/arm/totest",
        "ibs": f"registry.suse.de/suse/{DISTNAME}/update/bci",
        "dso": "registry1.dso.mil/ironbank/suse",
        "ibs-cr": ibs_cr_project,
        "ibs-released": "registry.suse.com",
    }[TARGET]


BCI_REPO_NAME = "SLE_BCI"
if OS_VERSION == "tumbleweed":
    BCI_REPO_NAME = "repo-oss"


def create_container_version_mark(
    available_versions: Iterable[str],
) -> MarkDecorator:
    """Creates a pytest mark for a container that is only available for a
    certain SLE version.

    Args:

    available_versions: iterable of versions for which this container is
        available. Each version must be in the form ``15.4`` for SLE 15 SP4,
        ``15.3`` for SLE 15 SP3 and so on
    """
    for ver in available_versions:
        if ver.startswith("15") and ver[:2] == str(OS_MAJOR_VERSION):
            assert (
                ver[:2] == str(OS_MAJOR_VERSION)
                and len(ver.partition("-")[0].split(".")) == 2
                and int(ver.partition("-")[0].split(".")[1]) >= 3
            ), f"invalid version {ver} specified in {available_versions}"
    return pytest.mark.skipif(
        OS_VERSION not in available_versions,
        reason=f"This container is not available for {OS_VERSION}, only for "
        + ", ".join(available_versions),
    )


#: URL to the SLE_BCI repository
BCI_DEVEL_REPO = os.getenv("BCI_DEVEL_REPO")


if BCI_DEVEL_REPO is None:
    if OS_VERSION == "tumbleweed":
        BCI_DEVEL_REPO = "http://download.opensuse.org/tumbleweed/repo/oss/"
    else:
        # from SLE 15 SP6 onward we use the unauthenticated CDN
        cdn_prefix = "public-dl" if OS_SP_VERSION >= 6 else "updates"
        BCI_DEVEL_REPO = f"https://{cdn_prefix}.suse.com/SUSE/Products/SLE-BCI/{OS_MAJOR_VERSION}-SP{OS_SP_VERSION}/{LOCALHOST.system_info.arch}/product/"
    _BCI_REPLACE_REPO_CONTAINERFILE = ""
else:
    bci_repo_path = f"/etc/zypp/repos.d/{BCI_REPO_NAME}.repo"
    bci_repo_replace = "${line/baseurl*/baseurl = " + BCI_DEVEL_REPO + "}"
    _BCI_REPLACE_REPO_CONTAINERFILE = f"""RUN if [ -e {bci_repo_path} ]; then \\
        while IFS= read -r line; do \\
            echo \"{bci_repo_replace}\" >> {bci_repo_path}.tmp; \\
        done < {bci_repo_path}; \\
        mv {bci_repo_path}.tmp {bci_repo_path}; \\
    fi"""

assert BCI_DEVEL_REPO, "BCI_DEVEL_REPO must be set at this point"

_IMAGE_TYPE_T = Literal["dockerfile", "kiwi"]


def _get_repository_name(image_type: _IMAGE_TYPE_T) -> str:
    if TARGET in ("dso", "ibs-released"):
        return ""
    if OS_VERSION == "15.6-ai" and TARGET == "ibs-cr":
        return "images/"
    if not OS_VERSION.startswith("16") and TARGET == "ibs-cr":
        return "images/"
    if TARGET in ("factory-totest", "factory-arm-totest"):
        return "containers/"
    if image_type == "dockerfile":
        return "containerfile/"
    if image_type == "kiwi":
        return "images/"
    raise AssertionError(f"invalid image_type: {image_type}")


@enum.unique
class ImageType(enum.Enum):
    """BCI type enumeration defining to which BCI class this container image
    belongs. It primarily influences whether the image specific labels appear as
    ``com.suse.bci`` or ``com.suse.application``.

    """

    LANGUAGE_STACK = enum.auto()
    SAC_LANGUAGE_STACK = enum.auto()
    APPLICATION = enum.auto()
    SAC_APPLICATION = enum.auto()
    OS = enum.auto()
    OS_LTSS = enum.auto()

    def __str__(self) -> str:
        if self.value == ImageType.OS_LTSS:
            return "suse/ltss"
        if self.value == ImageType.APPLICATION.value:
            return "application"
        if self.value == ImageType.SAC_APPLICATION.value:
            return "application"
        return "bci"


def create_BCI(
    build_tag: str,
    image_type: _IMAGE_TYPE_T = "dockerfile",
    available_versions: Optional[Sequence[str]] = None,
    extra_marks: Optional[Sequence[MarkDecorator]] = None,
    bci_type: ImageType = ImageType.LANGUAGE_STACK,
    container_user: Optional[str] = None,
    **kwargs,
) -> ParameterSet:
    """Creates a DerivedContainer wrapped in a pytest.param for the BCI with the
    given ``build_tag``.

    Args:
        image_type: define whether this image is build from a :file:`Dockerfile`
            or :file:`kiwi.xml`

        build_tag: the main build tag set for this image (it can be found at the
            top of the :file:`Dockerfile` or :file:`kiwi.xml`)

        available_versions: an optional list of operating system versions, for
            which this container image is available. Use this for container
            images that were not part of older SLE releases.

        extra_marks: an optional sequence of marks that should be applied to
            this container image (e.g. to skip it on certain architectures)

        bci_type: Defines whether this is a language, application or OS
            container. Language and application containers are automatically
            restricted to the tumbleweed OS versions.

        **kwargs: additional keyword arguments are forwarded to the constructor
            of the :py:class:`~pytest_container.DerivedContainer`
    """
    build_tag_base = build_tag.rpartition("/")[2]
    marks = []
    if extra_marks:
        for m in extra_marks:
            marks.append(m)

    if bci_type in (ImageType.SAC_APPLICATION, ImageType.SAC_LANGUAGE_STACK):
        marks.append(
            pytest.mark.skipif(
                condition=LOCALHOST.system_info.arch
                not in ("x86_64", "aarch64"),
                reason="Application collection containers are only available for x86_64 and aarch64",
            )
        )

    # Ironbank currently has only the "bci-base" image and nothing else, so
    # skip all other tests
    if TARGET == "dso" and (
        bci_type != ImageType.OS or "bci-base" not in build_tag
    ):
        marks.append(
            pytest.mark.skip(
                reason="This container is not available on Ironbank",
            )
        )

    if bci_type not in (ImageType.OS, ImageType.OS_LTSS):
        if available_versions:
            for ver in available_versions:
                if ver not in ALLOWED_NONBASE_OS_VERSIONS:
                    raise ValueError(
                        f"Invalid os version for a language or application stack container: {ver}"
                    )
        else:
            available_versions = list(_DEFAULT_NONBASE_OS_VERSIONS)
    else:
        if available_versions:
            for ver in available_versions:
                if ver not in ALLOWED_BASE_OS_VERSIONS:
                    raise ValueError(
                        f"Invalid os version {ver} for base container: {build_tag}"
                    )
        else:
            available_versions = list(_DEFAULT_BASE_OS_VERSIONS)

    if available_versions:
        marks.append(create_container_version_mark(available_versions))

    # only try to grab the mark from the build tag for containers that are
    # available for this os version, otherwise we get bogus errors for missing
    # marks
    if OS_VERSION in (
        available_versions or list(_DEFAULT_NONBASE_OS_VERSIONS)
    ):
        marks.append(pytest.mark.__getattr__(build_tag_base.replace(":", "_")))

    if TARGET == "manual":
        baseurl = os.getenv("CONTAINER_URL")
        if not baseurl:
            raise ValueError("Missing CONTAINER_URL for TARGET manual")
    elif OS_VERSION == "tumbleweed":
        if bci_type in (ImageType.APPLICATION, ImageType.SAC_APPLICATION):
            baseurl = (
                f"{BASEURL}/{_get_repository_name(image_type)}{build_tag}"
            )
        else:
            baseurl = f"{BASEURL}/{_get_repository_name(image_type)}opensuse/{build_tag}"
    else:
        baseurl = f"{BASEURL}/{_get_repository_name(image_type)}{build_tag}"

    if bci_type == ImageType.OS_LTSS:
        containerfile = ""
    else:
        if container_user:
            containerfile = f"USER root\n{_BCI_REPLACE_REPO_CONTAINERFILE}\nUSER {container_user}"
        else:
            containerfile = _BCI_REPLACE_REPO_CONTAINERFILE

    return pytest.param(
        DerivedContainer(
            base=baseurl,
            containerfile=containerfile,
            **kwargs,
        ),
        marks=marks,
        id=f"{build_tag} from {baseurl}",
    )


KIWI_CONTAINERS = [
    create_BCI(build_tag=f"bci/kiwi:{tag}", available_versions=(ver,))
    for ver, tag in (
        ("15.6", "9.24"),
        ("15.7", "9.24"),
        ("16.0", "10.1"),
        ("tumbleweed", "latest"),
    )
]

BASE_FIPS_CONTAINERS = []
LTSS_BASE_CONTAINERS = []
LTSS_BASE_FIPS_CONTAINERS = []

if OS_VERSION == "tumbleweed":
    BASE_CONTAINER = create_BCI(
        build_tag="tumbleweed:latest",
        image_type="kiwi",
        bci_type=ImageType.OS,
    )
    BASE_FIPS_CONTAINERS.append(
        create_BCI(
            build_tag=f"{BCI_CONTAINER_PREFIX}/bci-base-fips:{OS_CONTAINER_TAG}",
            bci_type=ImageType.OS,
            available_versions=["tumbleweed"],
        )
    )
else:
    BASE_CONTAINER = create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/bci-base:{OS_CONTAINER_TAG}",
        image_type="kiwi",
        bci_type=ImageType.OS,
    )
    if TARGET not in ("dso",):
        BASE_FIPS_CONTAINERS.append(
            create_BCI(
                build_tag=f"{BCI_CONTAINER_PREFIX}/bci-base-fips:{OS_CONTAINER_TAG}",
                bci_type=ImageType.OS,
                available_versions=[
                    ver
                    for ver in _DEFAULT_BASE_OS_VERSIONS
                    if ver not in ("15.5",)
                ],
            )
        )
    if TARGET in ("ibs", "ibs-cr", "ibs-released"):
        LTSS_BASE_CONTAINERS.extend(
            create_BCI(
                build_tag=f"{APP_CONTAINER_PREFIX}/ltss/sle{sp}/bci-base:{OS_CONTAINER_TAG}",
                available_versions=[sp],
                image_type="kiwi",
                extra_marks=[pytest.mark.__getattr__(f"bci-base_{sp}-ltss")],
                bci_type=ImageType.OS_LTSS,
            )
            for sp in ("15.3", "15.4", "15.5")
        )
        LTSS_BASE_FIPS_CONTAINERS.extend(
            create_BCI(
                build_tag=f"{APP_CONTAINER_PREFIX}/ltss/sle{sp}/bci-base-fips:{OS_CONTAINER_TAG}",
                available_versions=[sp],
                bci_type=ImageType.OS_LTSS,
            )
            for sp in ("15.3", "15.4")
        )

MINIMAL_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-minimal:{OS_CONTAINER_TAG}",
    image_type="kiwi",
    bci_type=ImageType.OS,
)
MICRO_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-micro:{OS_CONTAINER_TAG}",
    image_type="kiwi",
    bci_type=ImageType.OS,
)
BUSYBOX_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-busybox:{OS_CONTAINER_TAG}",
    image_type="kiwi",
    custom_entry_point="/bin/sh",
    bci_type=ImageType.OS,
)

# The very last container in this list needs to be available for all
# tested OSes
GOLANG_CONTAINERS = (
    [
        create_BCI(
            build_tag=f"{BCI_CONTAINER_PREFIX}/golang:{golang_version}",
            extra_marks=[pytest.mark.__getattr__(f"golang_{stability}")],
            available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
        )
        for golang_version, stability in (
            ("oldstable-openssl", "oldstable"),
            ("stable-openssl", "stable"),
        )
    ]
    + [
        create_BCI(
            build_tag=f"{BCI_CONTAINER_PREFIX}/golang:{golang_version}",
            extra_marks=[
                pytest.mark.__getattr__(f"golang_{golang_version}"),
                pytest.mark.skip(
                    reason="There is no unstable golang at the moment"
                ),
            ],
            available_versions=["tumbleweed"],
        )
        for golang_version in ("unstable",)
    ]
    + [
        create_BCI(
            build_tag=f"{BCI_CONTAINER_PREFIX}/golang:{stability}",
        )
        for stability in ("oldstable", "stable")
    ]
)

OPENJDK_11_CONTAINER = create_BCI(
    build_tag="bci/openjdk:11", available_versions=["tumbleweed"]
)
OPENJDK_DEVEL_11_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:11",
    available_versions=["tumbleweed"],
    custom_entry_point="/bin/sh",
)
OPENJDK_17_CONTAINER = create_BCI(
    build_tag="bci/openjdk:17", available_versions=["tumbleweed", "15.6"]
)
OPENJDK_DEVEL_17_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:17",
    available_versions=["tumbleweed", "15.6"],
    custom_entry_point="/bin/sh",
)
OPENJDK_21_CONTAINER = create_BCI(
    build_tag="bci/openjdk:21", available_versions=["15.6", "tumbleweed"]
)
OPENJDK_DEVEL_21_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:21",
    available_versions=["15.6", "tumbleweed"],
    custom_entry_point="/bin/sh",
)
OPENJDK_23_CONTAINER = create_BCI(
    build_tag="bci/openjdk:23", available_versions=["tumbleweed"]
)
OPENJDK_DEVEL_23_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:23", available_versions=["tumbleweed"]
)


OPENJDK_CONTAINERS = [
    OPENJDK_11_CONTAINER,
    OPENJDK_DEVEL_11_CONTAINER,
    OPENJDK_17_CONTAINER,
    OPENJDK_DEVEL_17_CONTAINER,
    OPENJDK_21_CONTAINER,
    OPENJDK_DEVEL_21_CONTAINER,
    OPENJDK_23_CONTAINER,
    OPENJDK_DEVEL_23_CONTAINER,
]

NODEJS_20_CONTAINER = create_BCI(
    build_tag="bci/nodejs:20",
    available_versions=["15.6"],
)

NODEJS_22_CONTAINER = create_BCI(
    build_tag="bci/nodejs:22",
    available_versions=["tumbleweed", "15.6", "15.7"],
)

NODEJS_CONTAINERS = [
    NODEJS_20_CONTAINER,
    NODEJS_22_CONTAINER,
]

PYTHON_WITH_PIPX_CONTAINERS = [
    create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/python:{ver}",
        available_versions=versions,
    )
    for ver, versions in (
        ("3.12", ["15.6", "tumbleweed"]),
        ("3.13", ["15.7", "tumbleweed"]),
    )
]

PYTHON_CONTAINERS = PYTHON_WITH_PIPX_CONTAINERS + [
    create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/python:{ver}",
        available_versions=versions,
    )
    for ver, versions in (
        ("3.6", ["15.6"]),
        ("3.11", _DEFAULT_NONBASE_OS_VERSIONS),
    )
]

# Python containers on SUSE Application Collection
SAC_PYTHON_CONTAINERS = [
    create_BCI(
        build_tag=f"{SAC_CONTAINER_PREFIX}/python:{ver}",
        available_versions=versions,
        bci_type=ImageType.SAC_LANGUAGE_STACK,
    )
    for ver, versions in (("3.9", ["15.6"]), ("3.11", ["15.6"]))
]

RUBY_25_CONTAINER = create_BCI(
    build_tag="bci/ruby:2.5", available_versions=["15.6"]
)

RUBY_LATEST_CONTAINER = create_BCI(
    build_tag="bci/ruby:latest", available_versions=["tumbleweed"]
)

RUBY_CONTAINERS = [RUBY_25_CONTAINER, RUBY_LATEST_CONTAINER]

_DOTNET_SKIP_ARCH_MARK = pytest.mark.skipif(
    LOCALHOST.system_info.arch != "x86_64",
    reason="The .Net containers are only available on x86_64",
)

DOTNET_SDK_8_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:8.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_9_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:9.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_8_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:8.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_9_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:9.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_8_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:8.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_9_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:9.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)


RUST_CONTAINERS = [
    create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/rust:{rust_version}",
    )
    for rust_version in ("oldstable", "stable")
]

INIT_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-init:{OS_CONTAINER_TAG}",
    bci_type=ImageType.OS,
    healthcheck_timeout=timedelta(seconds=240),
    extra_marks=[
        pytest.mark.skipif(
            DOCKER_SELECTED,
            reason="only podman is supported, systemd is broken with docker.",
        )
    ],
)

PCP_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/pcp:{ver}",
        extra_marks=[
            pytest.mark.skipif(
                DOCKER_SELECTED, reason="only podman is supported"
            )
        ],
        forwarded_ports=[PortForwarding(container_port=44322)],
        available_versions=os_ver,
        healthcheck_timeout=timedelta(seconds=240),
        extra_launch_args=["--systemd", "always"],
        bci_type=ImageType.APPLICATION,
    )
    for ver, os_ver in (
        ("6", ["15.6"]),
        ("6", ["tumbleweed"]),
    )
]

CONTAINER_389DS_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/389-ds:{ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=[os_ver],
        healthcheck_timeout=timedelta(seconds=240),
        extra_environment_variables={"SUFFIX_NAME": "dc=example,dc=com"},
        forwarded_ports=[PortForwarding(container_port=3389)],
    )
    for ver, os_ver in (
        ("2.2", "15.6"),
        ("3.1", "tumbleweed"),
    )
]

PHP_8_CLI = create_BCI(build_tag="bci/php:8")
PHP_8_APACHE = create_BCI(build_tag="bci/php-apache:8")
PHP_8_FPM = create_BCI(build_tag="bci/php-fpm:8")

MARIADB_ROOT_PASSWORD = "'88tpw-n!t-s$$cr`t!"

_MARIADB_VERSION_OS_MATRIX: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("10.11", ("15.6", "15.7")),
    ("11.6", ("tumbleweed",)),
)

MARIADB_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/mariadb:{mariadb_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=os_versions,
        forwarded_ports=[PortForwarding(container_port=3306)],
        extra_environment_variables={
            "MARIADB_ROOT_PASSWORD": MARIADB_ROOT_PASSWORD
        },
    )
    for mariadb_ver, os_versions in _MARIADB_VERSION_OS_MATRIX
]

MARIADB_CLIENT_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/mariadb-client:{mariadb_client_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=os_versions,
        custom_entry_point="/bin/sh",
    )
    for mariadb_client_ver, os_versions in _MARIADB_VERSION_OS_MATRIX
]

POSTFIX_CONTAINERS = [
    create_BCI(
        build_tag=f"{SAC_CONTAINER_PREFIX}/postfix:{postfix_ver}",
        bci_type=ImageType.SAC_APPLICATION,
        available_versions=os_versions,
        forwarded_ports=[PortForwarding(container_port=25)],
        extra_environment_variables={"SERVER_HOSTNAME": "localhost"},
    )
    for postfix_ver, os_versions in (
        (3.8, ["15.6"]),
        (3.9, ["tumbleweed"]),
    )
]

POSTGRES_PASSWORD = "n0ts3cr3t"

POSTGRESQL_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/postgres:{pg_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=pg_versions,
        forwarded_ports=[PortForwarding(container_port=5432)],
        extra_environment_variables={"POSTGRES_PASSWORD": POSTGRES_PASSWORD},
        # https://github.com/SUSE/BCI-tests/issues/647
        healthcheck_timeout=(
            timedelta(minutes=6)
            if LOCALHOST.system_info.arch == "ppc64le"
            else None
        ),
    )
    for pg_ver, pg_versions in (
        (14, ["tumbleweed"]),
        (15, ["tumbleweed"]),
        (16, _DEFAULT_NONBASE_OS_VERSIONS),
        (17, ["15.6", "tumbleweed"]),
    )
]

DISTRIBUTION_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/registry:2.8",
    bci_type=ImageType.APPLICATION,
    image_type="kiwi",
    forwarded_ports=[PortForwarding(container_port=5000)],
    volume_mounts=[ContainerVolume(container_path="/var/lib/docker-registry")],
    # FIXME: https://github.com/SUSE/BCI-tests/issues/647, Default timeout is 4 minutes
    healthcheck_timeout=(
        timedelta(minutes=8)
        if LOCALHOST.system_info.arch == "ppc64le"
        else None
    ),
)

if OS_VERSION in ("15.6", "15.7", "basalt"):
    _GIT_APP_VERSION = "2.43"
elif OS_VERSION in ("15.5", "15.4"):
    _GIT_APP_VERSION = "2.35"
else:
    _GIT_APP_VERSION = "latest"

GIT_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/git:{_GIT_APP_VERSION}",
    bci_type=ImageType.APPLICATION,
)

_HELM_APP_VERSION = "latest" if OS_VERSION == "tumbleweed" else "3"

HELM_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/helm:{_HELM_APP_VERSION}",
    bci_type=ImageType.APPLICATION,
    custom_entry_point="/bin/sh",
)

_COSIGN_VERSION: str = "2.4"
COSIGN_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/cosign:{_COSIGN_VERSION}",
        bci_type=ImageType.APPLICATION,
        custom_entry_point="/bin/sh",
    )
]

_NGINX_APP_VERSION = "latest" if OS_VERSION == "tumbleweed" else "1.21"

NGINX_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/nginx:{_NGINX_APP_VERSION}",
    bci_type=ImageType.APPLICATION,
    forwarded_ports=[PortForwarding(container_port=80)],
)

_KUBECTL_VERSION_OS_MATRIX: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("1.28", ("15.6", "15.7")),
    ("1.30", ("15.7",)),
    ("1.29", ("tumbleweed",)),
    ("1.30", ("tumbleweed",)),
    ("1.31", ("tumbleweed",)),
    ("1.32", ("tumbleweed",)),
)

KUBECTL_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/kubectl:{kubectl_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=os_versions,
        custom_entry_point="/bin/sh",
    )
    for kubectl_ver, os_versions in _KUBECTL_VERSION_OS_MATRIX
]

_KEA_VERSION_OS_MATRIX: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("2.6", ("tumbleweed", "15.7")),
)

KEA_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/kea:{kea_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=os_versions,
    )
    for kea_ver, os_versions in _KEA_VERSION_OS_MATRIX
]

if OS_VERSION in ("16.0",):
    KERNEL_MODULE_CONTAINER = create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/bci-sle16-kernel-module-devel:{OS_CONTAINER_TAG}",
        available_versions=["16.0"],
        bci_type=ImageType.OS,
    )
else:
    KERNEL_MODULE_CONTAINER = create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/bci-sle15-kernel-module-devel:{OS_CONTAINER_TAG}",
        available_versions=["15.6", "15.7"],
        bci_type=ImageType.OS,
    )

GCC_CONTAINERS = [
    create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/gcc:{gcc_version}",
        available_versions=os_versions,
    )
    for gcc_version, os_versions in (
        (13, ("tumbleweed",)),
        (14, ("15.6", "15.7", "tumbleweed")),
    )
]

APACHE_TOMCAT_10_CONTAINERS = [
    create_BCI(
        build_tag=f"{SAC_CONTAINER_PREFIX}/apache-tomcat:10.1-openjdk{openjdk_version}",
        bci_type=ImageType.SAC_APPLICATION,
        available_versions=("15.6",),
        forwarded_ports=[PortForwarding(container_port=8080)],
        container_user="tomcat",
    )
    for openjdk_version in (21, 17, 11)
] + [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/apache-tomcat:10.1-openjdk{openjdk_version}",
        bci_type=ImageType.APPLICATION,
        available_versions=("tumbleweed",),
        forwarded_ports=[PortForwarding(container_port=8080)],
    )
    for openjdk_version in (23, 21, 17)
]

APACHE_TOMCAT_9_CONTAINERS = [
    create_BCI(
        build_tag=f"{SAC_CONTAINER_PREFIX}/apache-tomcat:9-openjdk{openjdk_version}",
        bci_type=ImageType.SAC_APPLICATION,
        available_versions=("15.6",),
        forwarded_ports=[PortForwarding(container_port=8080)],
        container_user="tomcat",
    )
    for openjdk_version in (21, 17, 11, 8)
] + [
    create_BCI(
        build_tag=f"{SAC_CONTAINER_PREFIX}/apache-tomcat:9-openjdk{openjdk_version}",
        bci_type=ImageType.APPLICATION,
        available_versions=("tumbleweed",),
        forwarded_ports=[PortForwarding(container_port=8080)],
    )
    for openjdk_version in (21, 17)
]

TOMCAT_CONTAINERS = [
    *APACHE_TOMCAT_9_CONTAINERS,
    *APACHE_TOMCAT_10_CONTAINERS,
]

DOTNET_CONTAINERS = [
    DOTNET_SDK_8_0_CONTAINER,
    DOTNET_SDK_9_0_CONTAINER,
    DOTNET_ASPNET_8_0_CONTAINER,
    DOTNET_ASPNET_9_0_CONTAINER,
    DOTNET_RUNTIME_8_0_CONTAINER,
    DOTNET_RUNTIME_9_0_CONTAINER,
]

SPACK_CONTAINERS = [
    create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/spack:{tag}",
        available_versions=[f"{ver}"],
    )
    for ver, tag in (("15.6", "0.23"), ("15.7", "0.23"))
]

PROMETHEUS_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/prometheus:{tag}",
        bci_type=ImageType.APPLICATION,
        forwarded_ports=[PortForwarding(container_port=9090)],
        available_versions=versions,
    )
    for versions, tag in (
        (("15.6",), "2"),
        (("15.7",), "2"),
        (("tumbleweed",), "3"),
    )
]

ALERTMANAGER_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/alertmanager:{tag}",
        bci_type=ImageType.APPLICATION,
        forwarded_ports=[PortForwarding(container_port=9093)],
        available_versions=versions,
    )
    for versions, tag in (
        (("15.6",), "0.26"),
        (("15.7",), "0.26"),
        (("tumbleweed",), "latest"),
    )
]

BLACKBOX_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/blackbox_exporter:{tag}",
        bci_type=ImageType.APPLICATION,
        forwarded_ports=[PortForwarding(container_port=9115)],
        available_versions=versions,
    )
    for versions, tag in ((("15.6", "15.7", "tumbleweed"), "0.24"),)
]

GRAFANA_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/grafana:{tag}",
        bci_type=ImageType.APPLICATION,
        forwarded_ports=[PortForwarding(container_port=3000)],
        available_versions=versions,
    )
    for versions, tag in (
        (("15.6",), "10"),
        (("15.7",), "10"),
        (("tumbleweed",), "11"),
    )
]

OLLAMA_CONTAINER = create_BCI(
    build_tag=f"{SAC_CONTAINER_PREFIX}/ollama:0.5",
    bci_type=ImageType.SAC_APPLICATION,
    available_versions=["15.6-ai"],
    forwarded_ports=[PortForwarding(container_port=11434)],
)

OPENWEBUI_CONTAINER = create_BCI(
    build_tag=f"{SAC_CONTAINER_PREFIX}/open-webui:0.3",
    bci_type=ImageType.SAC_APPLICATION,
    available_versions=["15.6-ai"],
    forwarded_ports=[PortForwarding(container_port=8080)],
)

MILVUS_CONTAINER = create_BCI(
    build_tag=f"{SAC_CONTAINER_PREFIX}/milvus:2.4",
    bci_type=ImageType.SAC_APPLICATION,
    available_versions=["15.6-ai"],
    custom_entry_point="/bin/bash",
)

PYTORCH_CONTAINER = create_BCI(
    build_tag=f"{SAC_CONTAINER_PREFIX}/pytorch:2.5",
    bci_type=ImageType.SAC_APPLICATION,
    available_versions=["15.6-ai"],
    custom_entry_point="/bin/bash",
)


STUNNEL_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/stunnel:5",
    bci_type=ImageType.APPLICATION,
    custom_entry_point="/bin/sh",
    available_versions=["15.6", "15.7", "tumbleweed"],
)


CONTAINERS_WITH_ZYPPER = (
    [
        BASE_CONTAINER,
        INIT_CONTAINER,
        KERNEL_MODULE_CONTAINER,
        NGINX_CONTAINER,
        PHP_8_APACHE,
        PHP_8_CLI,
        PHP_8_FPM,
        OPENWEBUI_CONTAINER,
    ]
    + ALERTMANAGER_CONTAINERS
    + BASE_FIPS_CONTAINERS
    + BLACKBOX_CONTAINERS
    + CONTAINER_389DS_CONTAINERS
    + GCC_CONTAINERS
    + GOLANG_CONTAINERS
    + GRAFANA_CONTAINERS
    + KIWI_CONTAINERS
    + LTSS_BASE_CONTAINERS
    + LTSS_BASE_FIPS_CONTAINERS
    + NODEJS_CONTAINERS
    + OPENJDK_CONTAINERS
    + PCP_CONTAINERS
    + PROMETHEUS_CONTAINERS
    + PYTHON_CONTAINERS
    + SAC_PYTHON_CONTAINERS
    + RUBY_CONTAINERS
    + RUST_CONTAINERS
    + SPACK_CONTAINERS
    + (DOTNET_CONTAINERS if LOCALHOST.system_info.arch == "x86_64" else [])
    + KEA_CONTAINERS
)

#: all containers with zypper and with the flag to launch them as root
CONTAINERS_WITH_ZYPPER_AS_ROOT = []
for param in CONTAINERS_WITH_ZYPPER:
    # only modify the user for containers where `USER` is explicitly set,
    # atm this is no container
    if param not in []:
        CONTAINERS_WITH_ZYPPER_AS_ROOT.append(param)
    else:
        ctr, marks = container_and_marks_from_pytest_param(param)
        CONTAINERS_WITH_ZYPPER_AS_ROOT.append(
            pytest.param(
                DerivedContainer(
                    base=ctr,
                    extra_launch_args=(
                        (ctr.extra_launch_args or []) + ["--user", "root"]
                    ),
                ),
                marks=marks,
            )
        )


CONTAINERS_WITHOUT_ZYPPER = [
    BUSYBOX_CONTAINER,
    DISTRIBUTION_CONTAINER,
    GIT_CONTAINER,
    HELM_CONTAINER,
    *COSIGN_CONTAINERS,
    MICRO_CONTAINER,
    MINIMAL_CONTAINER,
    OLLAMA_CONTAINER,
    MILVUS_CONTAINER,
    PYTORCH_CONTAINER,
    *POSTFIX_CONTAINERS,
    *TOMCAT_CONTAINERS,
    *POSTGRESQL_CONTAINERS,
    *MARIADB_CLIENT_CONTAINERS,
    *MARIADB_CONTAINERS,
    STUNNEL_CONTAINER,
    *KUBECTL_CONTAINERS,
]


# can't use sets here, because the list contents are mutable :-(
for ctr_with_zypp in CONTAINERS_WITH_ZYPPER:
    assert ctr_with_zypp not in CONTAINERS_WITHOUT_ZYPPER, (
        f"Container '{ctr_with_zypp.id}' is both in CONTAINERS_WITH_ZYPPER and CONTAINERS_WITHOUT_ZYPPER"
    )

for ctr_without_zypp in CONTAINERS_WITHOUT_ZYPPER:
    assert ctr_without_zypp not in CONTAINERS_WITH_ZYPPER, (
        f"Container '{ctr_without_zypp.id}' is both in CONTAINERS_WITH_ZYPPER and CONTAINERS_WITHOUT_ZYPPER"
    )

#: Containers with L3 support
# Tumbleweed has no concept of l3 support
# 15.7 is not yet released, so no l3 support either
if OS_VERSION in ("tumbleweed", "16.0", "15.7"):
    L3_CONTAINERS = ()
else:
    L3_CONTAINERS = (
        [
            BASE_CONTAINER,
            BUSYBOX_CONTAINER,
            DISTRIBUTION_CONTAINER,
            GIT_CONTAINER,
            HELM_CONTAINER,
            INIT_CONTAINER,
            MICRO_CONTAINER,
            MINIMAL_CONTAINER,
            NGINX_CONTAINER,
            PHP_8_APACHE,
            PHP_8_CLI,
            PHP_8_FPM,
            OLLAMA_CONTAINER,
            OPENWEBUI_CONTAINER,
            MILVUS_CONTAINER,
            PYTORCH_CONTAINER,
        ]
        + BASE_FIPS_CONTAINERS
        + CONTAINER_389DS_CONTAINERS
        + COSIGN_CONTAINERS
        + GCC_CONTAINERS
        + GOLANG_CONTAINERS
        + LTSS_BASE_CONTAINERS
        + LTSS_BASE_FIPS_CONTAINERS
        + MARIADB_CLIENT_CONTAINERS
        + MARIADB_CONTAINERS
        + NODEJS_CONTAINERS
        + OPENJDK_CONTAINERS
        + PCP_CONTAINERS
        + PYTHON_CONTAINERS
        + SAC_PYTHON_CONTAINERS
        + RUBY_CONTAINERS
        + RUST_CONTAINERS
        + SPACK_CONTAINERS
        + KUBECTL_CONTAINERS
    )

ACC_CONTAINERS = POSTGRESQL_CONTAINERS

#: Containers that are directly pulled from registry.suse.de
ALL_CONTAINERS = CONTAINERS_WITH_ZYPPER + CONTAINERS_WITHOUT_ZYPPER


if __name__ == "__main__":
    from typing import Set

    import tomllib

    custom_markers: Set[str] = set(
        tomllib.loads(
            (Path(__file__).parent.parent / "pyproject.toml").read_text()
        )["tool"]["pytest"]["ini_options"]["markers"]
    )

    def has_true_skipif(param: ParameterSet) -> bool:
        for mark in param.marks:
            if mark.name == "skipif" and mark.args and mark.args[0]:
                return True
        return False

    def has_xfail(param: ParameterSet) -> bool:
        for mark in param.marks:
            if mark.name == "xfail":
                return True
        return False

    for param in ALL_CONTAINERS:
        # don't check containers which are known broken or excluded
        if has_true_skipif(param) or has_xfail(param):
            continue

        ctr, marks = container_and_marks_from_pytest_param(param)
        for mark in marks or []:
            assert mark.name in custom_markers.union(
                {"xfail", "skipif", "skip"}
            ), (
                f"marker '{mark.name}' of '{ctr.get_base().baseurl}' not found in pyproject.toml"
            )
