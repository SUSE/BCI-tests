#!/usr/bin/env python3
import enum
import os
from datetime import timedelta
from typing import Iterable
from typing import List
from typing import Optional
from typing import Sequence

from pytest_container import container_and_marks_from_pytest_param
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param
from pytest_container.container import ContainerVolume
from pytest_container.container import PortForwarding
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
OS_VERSION = os.getenv("OS_VERSION", "15.5")

# Allowed os versions for base (non lang/non-app) containers
ALLOWED_BASE_OS_VERSIONS = (
    "15.3",
    "15.4",
    "15.5",
    "15.6",
    "basalt",
    "tumbleweed",
)

# Allowed os versions for Language and Application containers
ALLOWED_NONBASE_OS_VERSIONS = ("15.5", "15.6", "tumbleweed")

# Allowed os versions for SLE_BCI repo checks
ALLOWED_BCI_REPO_OS_VERSIONS = ("15.5", "15.6", "tumbleweed")

# Test Language and Application containers by default for these versions
_DEFAULT_NONBASE_SLE_VERSIONS = ("15.5", "15.6")

# Test Language and Application containers by default for these versions
_DEFAULT_NONBASE_OS_VERSIONS = ("15.5", "15.6", "tumbleweed")

assert sorted(ALLOWED_BASE_OS_VERSIONS) == list(
    ALLOWED_BASE_OS_VERSIONS
), f"list ALLOWED_OS_VERSIONS must be sorted, but got {ALLOWED_BASE_OS_VERSIONS}"

assert sorted(ALLOWED_NONBASE_OS_VERSIONS) == list(
    ALLOWED_NONBASE_OS_VERSIONS
), f"list ALLOWED_NONOS_VERSIONS must be sorted, but got {ALLOWED_NONBASE_OS_VERSIONS}"

if not (
    OS_VERSION in ALLOWED_BASE_OS_VERSIONS
    or OS_VERSION in ALLOWED_NONBASE_OS_VERSIONS
):
    raise ValueError(
        f"Invalid OS_VERSION: {OS_VERSION}, allowed values are: "
        + ", ".join(ALLOWED_BASE_OS_VERSIONS)
    )


if OS_VERSION == "tumbleweed":
    OS_MAJOR_VERSION = 17
    OS_SP_VERSION = 0
    OS_CONTAINER_TAG = "latest"
    APP_CONTAINER_PREFIX = "opensuse"
    BCI_CONTAINER_PREFIX = "bci"
    OS_VERSION_ID = None

    #: The Tumbleweed pretty name (from /etc/os-release)
    OS_PRETTY_NAME = os.getenv(
        "OS_PRETTY_NAME",
        "openSUSE Tumbleweed",
    )
elif OS_VERSION == "basalt":
    OS_MAJOR_VERSION = 16
    OS_SP_VERSION = 0
    OS_CONTAINER_TAG = "latest"
    APP_CONTAINER_PREFIX = "basalt"
    BCI_CONTAINER_PREFIX = "alp/bci"
    OS_VERSION_ID = "0.1"

    #: The Basalt pretty name (from /etc/os-release)
    OS_PRETTY_NAME = os.getenv(
        "OS_PRETTY_NAME",
        "ALP",
    )
else:
    APP_CONTAINER_PREFIX = "suse"
    BCI_CONTAINER_PREFIX = "bci"
    OS_CONTAINER_TAG = OS_VERSION
    OS_VERSION_ID = OS_VERSION

    OS_MAJOR_VERSION, OS_SP_VERSION = (
        int(ver) for ver in OS_VERSION.split(".")
    )

    #: The SLES 15 pretty name (from /etc/os-release)
    OS_PRETTY_NAME = os.getenv(
        "OS_PRETTY_NAME",
        f"SUSE Linux Enterprise Server {OS_MAJOR_VERSION} SP{OS_SP_VERSION}",
    )

    assert OS_MAJOR_VERSION == 15, (
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
    "ibs-released",
):
    if BASEURL is None:
        raise ValueError(
            f"Unknown target {TARGET} specified and BASEURL is not set, cannot continue"
        )
    if BASEURL.endswith("/"):
        BASEURL = BASEURL[:-1]
else:
    if OS_VERSION in ("basalt", "tumbleweed"):
        DISTNAME = OS_VERSION
    else:
        DISTNAME = f"sle-{OS_MAJOR_VERSION}-sp{OS_SP_VERSION}"
    BASEURL = {
        "obs": f"registry.opensuse.org/devel/bci/{DISTNAME}",
        "factory-totest": "registry.opensuse.org/opensuse/factory/totest",
        "ibs": f"registry.suse.de/suse/{DISTNAME}/update/bci",
        "dso": "registry1.dso.mil/ironbank/suse",
        "ibs-cr": f"registry.suse.de/suse/{DISTNAME}/update/cr/totest",
        "ibs-released": "registry.suse.com",
    }[TARGET]


BCI_REPO_NAME = "SLE_BCI"
if OS_VERSION == "tumbleweed":
    BCI_REPO_NAME = "repo-oss"
if OS_VERSION == "basalt":
    BCI_REPO_NAME = "repo-basalt"


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
        if ver[:2] == str(OS_MAJOR_VERSION):
            assert (
                ver[:2] == str(OS_MAJOR_VERSION)
                and len(ver.split(".")) == 2
                and int(ver.split(".")[1]) >= 3
            ), f"invalid version {ver} specified in {available_versions}"
    return pytest.mark.skipif(
        OS_VERSION not in available_versions,
        reason=f"This container is not available for {OS_VERSION}, only for "
        + ", ".join(available_versions),
    )


#: URL to the SLE_BCI repository
BCI_DEVEL_REPO = os.getenv("BCI_DEVEL_REPO")


if BCI_DEVEL_REPO is None:
    BCI_DEVEL_REPO = f"https://updates.suse.com/SUSE/Products/SLE-BCI/{OS_MAJOR_VERSION}-SP{OS_SP_VERSION}/{LOCALHOST.system_info.arch}/product/"
    _BCI_REPLACE_REPO_CONTAINERFILE = ""
else:
    _BCI_REPLACE_REPO_CONTAINERFILE = f"RUN sed -i 's|baseurl.*|baseurl={BCI_DEVEL_REPO}|' /etc/zypp/repos.d/{BCI_REPO_NAME}.repo"


_IMAGE_TYPE_T = Literal["dockerfile", "kiwi"]


def _get_repository_name(image_type: _IMAGE_TYPE_T) -> str:
    if TARGET in ("dso", "ibs-released"):
        return ""
    if TARGET == "ibs-cr":
        return "images/"
    if TARGET == "factory-totest":
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
    APPLICATION = enum.auto()
    OS = enum.auto()
    OS_LTSS = enum.auto()

    def __str__(self) -> str:
        if self.value == ImageType.OS_LTSS:
            return "suse/ltss"
        return (
            "application"
            if self.value == ImageType.APPLICATION.value
            else "bci"
        )


def create_BCI(
    build_tag: str,
    image_type: _IMAGE_TYPE_T = "dockerfile",
    available_versions: Optional[List[str]] = None,
    extra_marks: Optional[Sequence[MarkDecorator]] = None,
    bci_type: ImageType = ImageType.LANGUAGE_STACK,
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

    if available_versions:
        marks.append(create_container_version_mark(available_versions))

    # only try to grab the mark from the build tag for containers that are
    # available for this os version, otherwise we get bogus errors for missing
    # marks
    if OS_VERSION in (
        available_versions or list(_DEFAULT_NONBASE_OS_VERSIONS)
    ):
        marks.append(pytest.mark.__getattr__(build_tag_base.replace(":", "_")))

    if OS_VERSION == "tumbleweed":
        if bci_type == ImageType.APPLICATION:
            baseurl = (
                f"{BASEURL}/{_get_repository_name(image_type)}{build_tag}"
            )
        else:
            baseurl = f"{BASEURL}/{_get_repository_name(image_type)}opensuse/{build_tag}"
    else:
        baseurl = f"{BASEURL}/{_get_repository_name(image_type)}{build_tag}"

    return pytest.param(
        DerivedContainer(
            base=baseurl,
            containerfile=""
            if bci_type == ImageType.OS_LTSS
            else _BCI_REPLACE_REPO_CONTAINERFILE,
            **kwargs,
        ),
        marks=marks,
        id=f"{build_tag} from {baseurl}",
    )


LTSS_BASE_CONTAINERS = []
LTSS_BASE_FIPS_CONTAINERS = []

if OS_VERSION == "tumbleweed":
    BASE_CONTAINER = create_BCI(
        build_tag="tumbleweed:latest",
        image_type="kiwi",
        bci_type=ImageType.OS,
    )
else:
    BASE_CONTAINER = create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/bci-base:{OS_CONTAINER_TAG}",
        image_type="kiwi",
        bci_type=ImageType.OS,
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
            for sp in ("15.3", "15.4")
        )
        LTSS_BASE_FIPS_CONTAINERS.append(
            create_BCI(
                build_tag=f"{APP_CONTAINER_PREFIX}/ltss/sle15.3/bci-base-fips:{OS_CONTAINER_TAG}",
                available_versions=["15.3"],
                bci_type=ImageType.OS_LTSS,
            )
        )

MINIMAL_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-minimal:{OS_CONTAINER_TAG}",
    image_type="kiwi",
    available_versions=ALLOWED_BASE_OS_VERSIONS,
    bci_type=ImageType.OS,
)
MICRO_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-micro:{OS_CONTAINER_TAG}",
    image_type="kiwi",
    available_versions=ALLOWED_BASE_OS_VERSIONS,
    bci_type=ImageType.OS,
)
BUSYBOX_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-busybox:{OS_CONTAINER_TAG}",
    image_type="kiwi",
    available_versions=["15.4", "15.5", "15.6", "tumbleweed"],
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
            extra_marks=[pytest.mark.__getattr__(f"golang_{golang_version}")],
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
    build_tag="bci/openjdk:11", available_versions=["15.5", "tumbleweed"]
)
OPENJDK_DEVEL_11_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:11", available_versions=["15.5", "tumbleweed"]
)
OPENJDK_17_CONTAINER = create_BCI(
    build_tag="bci/openjdk:17", available_versions=["15.5", "tumbleweed"]
)
OPENJDK_DEVEL_17_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:17", available_versions=["15.5", "tumbleweed"]
)
OPENJDK_21_CONTAINER = create_BCI(
    build_tag="bci/openjdk:21", available_versions=["15.6", "tumbleweed"]
)
OPENJDK_DEVEL_21_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:21", available_versions=["15.6", "tumbleweed"]
)

OPENJDK_CONTAINERS = [
    OPENJDK_11_CONTAINER,
    OPENJDK_DEVEL_11_CONTAINER,
    OPENJDK_17_CONTAINER,
    OPENJDK_DEVEL_17_CONTAINER,
    OPENJDK_21_CONTAINER,
    OPENJDK_DEVEL_21_CONTAINER,
]

NODEJS_18_CONTAINER = create_BCI(
    build_tag="bci/nodejs:18", available_versions=["15.5"]
)
NODEJS_20_CONTAINER = create_BCI(
    build_tag="bci/nodejs:20",
    available_versions=_DEFAULT_NONBASE_OS_VERSIONS,
)

NODEJS_CONTAINERS = [
    NODEJS_18_CONTAINER,
    NODEJS_20_CONTAINER,
]

PYTHON36_CONTAINER = create_BCI(
    build_tag="bci/python:3.6", available_versions=["15.5"]
)
PYTHON310_CONTAINER = create_BCI(
    build_tag="bci/python:3.10", available_versions=["tumbleweed"]
)
PYTHON311_CONTAINER = create_BCI(build_tag="bci/python:3.11")

PYTHON312_CONTAINER = create_BCI(
    build_tag="bci/python:3.12", available_versions=["15.6", "tumbleweed"]
)

PYTHON_CONTAINERS = [
    PYTHON36_CONTAINER,
    PYTHON310_CONTAINER,
    PYTHON311_CONTAINER,
    PYTHON312_CONTAINER,
]

PYTHON_WITH_PIPX_CONTAINERS = [
    PYTHON310_CONTAINER,
    PYTHON311_CONTAINER,
]

RUBY_25_CONTAINER = create_BCI(
    build_tag="bci/ruby:2.5", available_versions=["15.5"]
)

RUBY_33_CONTAINER = create_BCI(
    build_tag="bci/ruby:3.3", available_versions=["tumbleweed"]
)

RUBY_CONTAINERS = [RUBY_25_CONTAINER, RUBY_33_CONTAINER]

_DOTNET_SKIP_ARCH_MARK = pytest.mark.skipif(
    LOCALHOST.system_info.arch != "x86_64",
    reason="The .Net containers are only available on x86_64",
)

DOTNET_SDK_6_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:6.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_7_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:7.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_8_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:8.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_6_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:6.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_7_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:7.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_8_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:8.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_6_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:6.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_7_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:7.0",
    available_versions=_DEFAULT_NONBASE_SLE_VERSIONS,
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_8_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:8.0",
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
    available_versions=["15.4", "15.5", "15.6", "tumbleweed"],
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
        ("5", ["15.5", "15.6"]),
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
        ("2.2", "15.5"),
        ("3.0", "tumbleweed"),
    )
]

PHP_8_CLI = create_BCI(build_tag="bci/php:8")
PHP_8_APACHE = create_BCI(build_tag="bci/php-apache:8")
PHP_8_FPM = create_BCI(build_tag="bci/php-fpm:8")

MARIADB_ROOT_PASSWORD = "'88tpw-n!t-s$$cr`t!"

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
    for mariadb_ver, os_versions in (
        ("10.11", ("15.6",)),
        ("10.6", ("15.5",)),
        ("11.2", ("tumbleweed",)),
    )
]

MARIADB_CLIENT_CONTAINERS = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/mariadb-client:{mariadb_client_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=os_versions,
        custom_entry_point="/bin/sh",
    )
    for mariadb_client_ver, os_versions in (
        ("10.11", ("15.6",)),
        ("10.6", ("15.5",)),
        ("11.2", ("tumbleweed",)),
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
    )
    for pg_ver, pg_versions in (
        (15, ["15.5", "tumbleweed"]),
        (16, ["15.5", "15.6", "tumbleweed"]),
    )
]

REPOCLOSURE_CONTAINER = DerivedContainer(
    base="registry.fedoraproject.org/fedora:latest",
    containerfile=rf"""RUN dnf -y install 'dnf-command(repoclosure)'
RUN rm -f /etc/yum.repos.d/*repo
RUN printf '[{BCI_REPO_NAME}]\n\
enabled=1\n\
name="SLE BCI"\n\
autorefresh=0\n\
baseurl={BCI_DEVEL_REPO}\n\
priority=100\n' > /etc/yum.repos.d/{BCI_REPO_NAME}.repo""",
)


DISTRIBUTION_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/registry:2.8",
    bci_type=ImageType.APPLICATION,
    image_type="kiwi",
    forwarded_ports=[PortForwarding(container_port=5000)],
    volume_mounts=[ContainerVolume(container_path="/var/lib/docker-registry")],
)

if OS_VERSION in ("15.6", "basalt"):
    _GIT_APP_VERSION = "2.43"
elif OS_VERSION in ("15.5", "15.4"):
    _GIT_APP_VERSION = "2.35"
else:
    _GIT_APP_VERSION = "latest"

GIT_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/git:{_GIT_APP_VERSION}",
    bci_type=ImageType.APPLICATION,
    image_type="kiwi",
)

_HELM_APP_VERSION = "latest" if OS_VERSION == "tumbleweed" else "3.13"

HELM_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/helm:{_HELM_APP_VERSION}",
    bci_type=ImageType.APPLICATION,
    custom_entry_point="/bin/sh",
    image_type="kiwi",
)

_NGINX_APP_VERSION = "latest" if OS_VERSION == "tumbleweed" else "1.21"

NGINX_CONTAINER = create_BCI(
    build_tag=f"{APP_CONTAINER_PREFIX}/nginx:{_NGINX_APP_VERSION}",
    bci_type=ImageType.APPLICATION,
    forwarded_ports=[PortForwarding(container_port=80)],
)

KERNEL_MODULE_CONTAINER = create_BCI(
    build_tag=f"{BCI_CONTAINER_PREFIX}/bci-sle15-kernel-module-devel:{OS_CONTAINER_TAG}",
    available_versions=["15.5", "15.6"],
    bci_type=ImageType.OS,
)

TOMCAT_9_CONTAINER, TOMCAT_10_CONTAINER = [
    create_BCI(
        build_tag=f"{APP_CONTAINER_PREFIX}/tomcat:{tomcat_ver}",
        bci_type=ImageType.APPLICATION,
        forwarded_ports=[PortForwarding(container_port=8080)],
    )
    for tomcat_ver in (9, 10)
]
TOMCAT_CONTAINERS = [TOMCAT_9_CONTAINER, TOMCAT_10_CONTAINER]

DOTNET_CONTAINERS = [
    DOTNET_SDK_6_0_CONTAINER,
    DOTNET_SDK_7_0_CONTAINER,
    DOTNET_SDK_8_0_CONTAINER,
    DOTNET_ASPNET_6_0_CONTAINER,
    DOTNET_ASPNET_7_0_CONTAINER,
    DOTNET_ASPNET_8_0_CONTAINER,
    DOTNET_RUNTIME_6_0_CONTAINER,
    DOTNET_RUNTIME_7_0_CONTAINER,
    DOTNET_RUNTIME_8_0_CONTAINER,
]

SPACK_CONTAINERS = [
    create_BCI(
        build_tag=f"{BCI_CONTAINER_PREFIX}/spack:{tag}",
        available_versions=[f"{ver}"],
    )
    for ver, tag in (("15.6", "0.21"),)
]

CONTAINERS_WITH_ZYPPER = (
    [
        BASE_CONTAINER,
        NGINX_CONTAINER,
        NODEJS_18_CONTAINER,
        NODEJS_20_CONTAINER,
        INIT_CONTAINER,
        PHP_8_APACHE,
        PHP_8_CLI,
        PHP_8_FPM,
        KERNEL_MODULE_CONTAINER,
    ]
    + PCP_CONTAINERS
    + LTSS_BASE_CONTAINERS
    + LTSS_BASE_FIPS_CONTAINERS
    + CONTAINER_389DS_CONTAINERS
    + PYTHON_CONTAINERS
    + RUBY_CONTAINERS
    + GOLANG_CONTAINERS
    + RUST_CONTAINERS
    + OPENJDK_CONTAINERS
    + MARIADB_CONTAINERS
    + MARIADB_CLIENT_CONTAINERS
    + POSTGRESQL_CONTAINERS
    + SPACK_CONTAINERS
    + TOMCAT_CONTAINERS
    + (DOTNET_CONTAINERS if LOCALHOST.system_info.arch == "x86_64" else [])
)

#: all containers with zypper and with the flag to launch them as root
CONTAINERS_WITH_ZYPPER_AS_ROOT = []
for param in CONTAINERS_WITH_ZYPPER:
    # only modify the user for containers where `USER` is explicitly set,
    # atm this is only tomcat
    if param not in TOMCAT_CONTAINERS:
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
    MINIMAL_CONTAINER,
    MICRO_CONTAINER,
    BUSYBOX_CONTAINER,
    HELM_CONTAINER,
    GIT_CONTAINER,
    DISTRIBUTION_CONTAINER,
]

#: Containers with L3 support
# Tumbleweed has no concept of l3 support
# SLE 15 SP6 is techpreview before GMC
if OS_VERSION in ("15.6", "tumbleweed"):
    L3_CONTAINERS = ()
else:
    L3_CONTAINERS = (
        [
            BASE_CONTAINER,
            MINIMAL_CONTAINER,
            MICRO_CONTAINER,
            GIT_CONTAINER,
            INIT_CONTAINER,
            BUSYBOX_CONTAINER,
            DISTRIBUTION_CONTAINER,
            NGINX_CONTAINER,
            HELM_CONTAINER,
            PHP_8_CLI,
            PHP_8_APACHE,
            PHP_8_FPM,
        ]
        + PCP_CONTAINERS
        + LTSS_BASE_CONTAINERS
        + LTSS_BASE_FIPS_CONTAINERS
        + CONTAINER_389DS_CONTAINERS
        + PYTHON_CONTAINERS
        + RUBY_CONTAINERS
        + GOLANG_CONTAINERS
        + NODEJS_CONTAINERS
        + RUST_CONTAINERS
        + OPENJDK_CONTAINERS
        + MARIADB_CLIENT_CONTAINERS
        + MARIADB_CONTAINERS
    )

ACC_CONTAINERS = POSTGRESQL_CONTAINERS

#: Containers that are directly pulled from registry.suse.de
ALL_CONTAINERS = CONTAINERS_WITH_ZYPPER + CONTAINERS_WITHOUT_ZYPPER


if __name__ == "__main__":
    import json

    def has_true_skipif(param: ParameterSet) -> bool:
        for mark in param.marks:
            if mark.name == "skipif" and mark.args[0]:
                return True
        return False

    def has_xfail(param: ParameterSet) -> bool:
        for mark in param.marks:
            if mark.name == "xfail":
                return True
        return False

    print(
        json.dumps(
            [
                container_from_pytest_param(cont).get_base().url
                for cont in ALL_CONTAINERS
                if (not has_true_skipif(cont) and not has_xfail(cont))
            ]
        )
    )
