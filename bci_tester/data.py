#!/usr/bin/env python3
import enum
import os
from datetime import timedelta
from typing import Iterable
from typing import List
from typing import Optional
from typing import Sequence

from pytest_container.container import container_from_pytest_param
from pytest_container.container import ContainerVolume
from pytest_container.container import PortForwarding

try:
    from typing import Literal
except ImportError:
    # typing.Literal is available on python3.8+
    # https://docs.python.org/3/library/typing.html#typing.Literal
    from typing_extensions import Literal

import pytest
from _pytest.mark.structures import MarkDecorator
from _pytest.mark.structures import ParameterSet
from pytest_container import DerivedContainer
from pytest_container.runtime import LOCALHOST

from bci_tester.runtime_choice import DOCKER_SELECTED


#: The operating system version as present in /etc/os-release & various other
#: places
OS_VERSION = os.getenv("OS_VERSION", "15.4")

ALLOWED_OS_VERSIONS = ("15.3", "15.4", "15.5")
_LANGUAGE_APPLICATION_STACK_OS_VERSIONS = ("15.4", "15.5")

assert sorted(ALLOWED_OS_VERSIONS) == list(
    ALLOWED_OS_VERSIONS
), f"list ALLOWED_OS_VERSIONS must be sorted, but got {ALLOWED_OS_VERSIONS}"

if OS_VERSION not in ALLOWED_OS_VERSIONS:
    raise ValueError(
        f"Invalid OS_VERSION: {OS_VERSION}, allowed values are: "
        + ", ".join(ALLOWED_OS_VERSIONS)
    )

OS_MAJOR_VERSION, OS_SP_VERSION = (int(ver) for ver in OS_VERSION.split("."))

#: The SLES 15 pretty name (from /etc/os-release)
OS_PRETTY_NAME = os.getenv(
    "OS_PRETTY_NAME",
    f"SUSE Linux Enterprise Server {OS_MAJOR_VERSION} SP{OS_SP_VERSION}",
)


assert (
    OS_MAJOR_VERSION == 15
), f"The tests are created for SLE 15 base images only, but got a request for SLE {OS_MAJOR_VERSION}"


#: value of the environment variable ``TARGET`` which defines whether we are
#: taking the images from OBS, IBS or the ``CR:ToTest`` project on IBS
TARGET = os.getenv("TARGET", "obs")

#: If no target is defined, then you have to supply your own registry BASEURL
#: via this variable instead
BASEURL = os.getenv("BASEURL")

if TARGET not in ("obs", "ibs", "ibs-cr", "dso"):
    if BASEURL is None:
        raise ValueError(
            f"Unknown target {TARGET} specified and BASEURL is not set, cannot continue"
        )
    if BASEURL.endswith("/"):
        BASEURL = BASEURL[:-1]
else:
    _SLE_SP = f"sle-{OS_MAJOR_VERSION}-sp{OS_SP_VERSION}"
    BASEURL = {
        "obs": f"registry.opensuse.org/devel/bci/{_SLE_SP}",
        "ibs": f"registry.suse.de/suse/{_SLE_SP}/update/bci",
        "dso": "registry1.dso.mil/ironbank/suse",
        "ibs-cr": f"registry.suse.de/suse/{_SLE_SP}/update/cr/totest",
    }[TARGET]


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
        assert (
            ver[:2] == str(OS_MAJOR_VERSION)
            and len(ver.split(".")) == 2
            and int(ver.split(".")[1]) >= 3
        ), f"invalid version {ver} specified in {available_versions}"
    return pytest.mark.skipif(
        OS_VERSION not in available_versions,
        reason=f"This container is not available for {OS_VERSION}, only for {', '.join(available_versions)}",
    )


#: URL to the SLE_BCI repository
BCI_DEVEL_REPO = os.getenv("BCI_DEVEL_REPO")
if BCI_DEVEL_REPO is None:
    BCI_DEVEL_REPO = f"https://updates.suse.com/SUSE/Products/SLE-BCI/{OS_MAJOR_VERSION}-SP{OS_SP_VERSION}/{LOCALHOST.system_info.arch}/product/"
    _BCI_CONTAINERFILE = ""
else:
    _BCI_CONTAINERFILE = f"RUN sed -i 's|baseurl.*|baseurl={BCI_DEVEL_REPO}|' /etc/zypp/repos.d/SLE_BCI.repo"


_IMAGE_TYPE_T = Literal["dockerfile", "kiwi"]


def _get_repository_name(image_type: _IMAGE_TYPE_T) -> str:
    if TARGET == "dso":
        return ""
    if TARGET == "ibs-cr":
        return "images/"
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

    def __str__(self) -> str:
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
            restricted to the latest OS versions.

        **kwargs: additional keyword arguments are forwarded to the constructor
            of the :py:class:`~pytest_container.DerivedContainer`
    """
    marks = [pytest.mark.__getattr__(build_tag.replace(":", "_"))]
    if extra_marks:
        for m in extra_marks:
            marks.append(m)

    if bci_type != ImageType.OS:
        if available_versions:
            for ver in available_versions:
                if ver not in _LANGUAGE_APPLICATION_STACK_OS_VERSIONS:
                    raise ValueError(
                        f"Invalid os version for a language or application stack container: {ver}"
                    )
            marks.append(create_container_version_mark(available_versions))
        else:
            marks.append(
                create_container_version_mark(
                    _LANGUAGE_APPLICATION_STACK_OS_VERSIONS
                )
            )

    elif available_versions is not None:
        marks.append(create_container_version_mark(available_versions))

    baseurl = f"{BASEURL}/{_get_repository_name(image_type)}{build_tag}"

    return pytest.param(
        DerivedContainer(
            base=baseurl,
            containerfile=_BCI_CONTAINERFILE,
            **kwargs,
        ),
        marks=marks,
        id=f"{build_tag} from {baseurl}",
    )


BASE_CONTAINER = create_BCI(
    build_tag=f"bci/bci-base:{OS_VERSION}",
    image_type="kiwi",
    bci_type=ImageType.OS,
)
MINIMAL_CONTAINER = create_BCI(
    build_tag=f"bci/bci-minimal:{OS_VERSION}",
    image_type="kiwi",
    available_versions=["15.4", "15.5"],
    bci_type=ImageType.OS,
)
MICRO_CONTAINER = create_BCI(
    build_tag=f"bci/bci-micro:{OS_VERSION}",
    image_type="kiwi",
    available_versions=["15.4", "15.5"],
    bci_type=ImageType.OS,
)
BUSYBOX_CONTAINER = create_BCI(
    build_tag=f"bci/bci-busybox:{OS_VERSION}",
    image_type="kiwi",
    available_versions=["15.4", "15.5"],
    custom_entry_point="/bin/sh",
    bci_type=ImageType.OS,
)

GOLANG_CONTAINERS = [
    create_BCI(build_tag=f"bci/golang:{golang_version}")
    for golang_version in ("1.19", "1.20")
]

OPENJDK_11_CONTAINER = create_BCI(
    build_tag="bci/openjdk:11", available_versions=["15.4"]
)
OPENJDK_DEVEL_11_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:11", available_versions=["15.4"]
)
OPENJDK_17_CONTAINER = create_BCI(
    build_tag="bci/openjdk:17", available_versions=["15.4"]
)
OPENJDK_DEVEL_17_CONTAINER = create_BCI(
    build_tag="bci/openjdk-devel:17", available_versions=["15.4"]
)
NODEJS_14_CONTAINER = create_BCI(
    build_tag="bci/nodejs:14", available_versions=["15.4"]
)
NODEJS_16_CONTAINER = create_BCI(
    build_tag="bci/nodejs:16", available_versions=["15.4"]
)
NODEJS_18_CONTAINER = create_BCI(
    build_tag="bci/nodejs:18", available_versions=["15.4"]
)

PYTHON36_CONTAINER = create_BCI(build_tag="bci/python:3.6")
PYTHON310_CONTAINER = create_BCI(
    build_tag="bci/python:3.10", available_versions=["15.4"]
)
PYTHON311_CONTAINER = create_BCI(
    build_tag="bci/python:3.11", available_versions=["15.5"]
)

PYTHON_CONTAINERS = [
    PYTHON36_CONTAINER,
    PYTHON310_CONTAINER,
    PYTHON311_CONTAINER,
]

RUBY_25_CONTAINER = create_BCI(build_tag="bci/ruby:2.5")

_DOTNET_SKIP_ARCH_MARK = pytest.mark.skipif(
    LOCALHOST.system_info.arch != "x86_64",
    reason="The .Net containers are only available on x86_64",
)

DOTNET_SDK_3_1_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:3.1",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_6_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:6.0",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_7_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-sdk:7.0",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)

DOTNET_ASPNET_3_1_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:3.1",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_6_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:6.0",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_7_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-aspnet:7.0",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)

DOTNET_RUNTIME_3_1_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:3.1",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_6_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:6.0",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_7_0_CONTAINER = create_BCI(
    build_tag="bci/dotnet-runtime:7.0",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)

RUST_CONTAINERS = [
    create_BCI(
        build_tag=f"bci/rust:{rust_version}", available_versions=["15.4"]
    )
    for rust_version in ("1.67", "1.68")
]

INIT_CONTAINER = create_BCI(
    build_tag=f"bci/bci-init:{OS_VERSION}",
    available_versions=["15.4", "15.5"],
    healthcheck_timeout=timedelta(seconds=240),
    extra_marks=[
        pytest.mark.skipif(
            DOCKER_SELECTED,
            reason="only podman is supported, systemd is broken with docker.",
        )
    ],
)

PCP_CONTAINER = create_BCI(
    build_tag="suse/pcp:5",
    available_versions=["15.4"],
    extra_marks=[
        pytest.mark.skipif(DOCKER_SELECTED, reason="only podman is supported")
    ],
    forwarded_ports=[PortForwarding(container_port=44322)],
    healthcheck_timeout=timedelta(seconds=240),
    extra_launch_args=[] if DOCKER_SELECTED else ["--systemd", "always"],
    bci_type=ImageType.APPLICATION,
)

CONTAINER_389DS = create_BCI(
    build_tag="suse/389-ds:2.0",
    bci_type=ImageType.APPLICATION,
    available_versions=["15.4"],
    healthcheck_timeout=timedelta(seconds=240),
    extra_environment_variables={"SUFFIX_NAME": "dc=example,dc=com"},
    forwarded_ports=[PortForwarding(container_port=3389)],
)

PHP_8_CLI = create_BCI(build_tag="bci/php:8", available_versions=["15.4"])
PHP_8_APACHE = create_BCI(
    build_tag="bci/php-apache:8", available_versions=["15.4"]
)
PHP_8_FPM = create_BCI(build_tag="bci/php-fpm:8", available_versions=["15.4"])

POSTGRES_PASSWORD = "n0ts3cr3t"

POSTGRESQL_CONTAINERS = [
    create_BCI(
        build_tag=f"suse/postgres:{pg_ver}",
        bci_type=ImageType.APPLICATION,
        available_versions=["15.4"],
        forwarded_ports=[PortForwarding(container_port=5432)],
        extra_environment_variables={"POSTGRES_PASSWORD": POSTGRES_PASSWORD},
    )
    for pg_ver in (10, 12, 13, 14)
]

REPOCLOSURE_CONTAINER = DerivedContainer(
    base="registry.fedoraproject.org/fedora:latest",
    containerfile=r"""RUN dnf -y install 'dnf-command(repoclosure)'
RUN rm -f /etc/yum.repos.d/*repo
RUN echo $'[SLE_BCI] \n\
enabled=1 \n\
name="SLE BCI" \n\
autorefresh=0 \n\
baseurl="""
    + BCI_DEVEL_REPO
    + r""" \n\
priority=100' > /etc/yum.repos.d/SLE_BCI.repo
""",
)


DISTRIBUTION_CONTAINER = create_BCI(
    build_tag="suse/registry:2.8",
    image_type="kiwi",
    available_versions=["15.4"],
    forwarded_ports=[PortForwarding(container_port=5000)],
    volume_mounts=[ContainerVolume(container_path="/var/lib/docker-registry")],
)

DOTNET_CONTAINERS = [
    DOTNET_SDK_3_1_CONTAINER,
    DOTNET_SDK_6_0_CONTAINER,
    DOTNET_SDK_7_0_CONTAINER,
    DOTNET_ASPNET_3_1_CONTAINER,
    DOTNET_ASPNET_6_0_CONTAINER,
    DOTNET_ASPNET_7_0_CONTAINER,
    DOTNET_RUNTIME_3_1_CONTAINER,
    DOTNET_RUNTIME_6_0_CONTAINER,
    DOTNET_RUNTIME_7_0_CONTAINER,
]
CONTAINERS_WITH_ZYPPER = (
    [
        BASE_CONTAINER,
        OPENJDK_11_CONTAINER,
        OPENJDK_DEVEL_11_CONTAINER,
        OPENJDK_17_CONTAINER,
        OPENJDK_DEVEL_17_CONTAINER,
        NODEJS_14_CONTAINER,
        NODEJS_16_CONTAINER,
        NODEJS_18_CONTAINER,
        PCP_CONTAINER,
        PYTHON36_CONTAINER,
        PYTHON310_CONTAINER,
        PYTHON311_CONTAINER,
        RUBY_25_CONTAINER,
        INIT_CONTAINER,
        CONTAINER_389DS,
        PHP_8_APACHE,
        PHP_8_CLI,
        PHP_8_FPM,
    ]
    + GOLANG_CONTAINERS
    + RUST_CONTAINERS
    + POSTGRESQL_CONTAINERS
    + (DOTNET_CONTAINERS if LOCALHOST.system_info.arch == "x86_64" else [])
)

CONTAINERS_WITHOUT_ZYPPER = [
    MINIMAL_CONTAINER,
    MICRO_CONTAINER,
    BUSYBOX_CONTAINER,
]

#: Containers with L3 support
L3_CONTAINERS = (
    [
        BASE_CONTAINER,
        MINIMAL_CONTAINER,
        MICRO_CONTAINER,
        INIT_CONTAINER,
        BUSYBOX_CONTAINER,
        NODEJS_14_CONTAINER,
        NODEJS_16_CONTAINER,
        NODEJS_18_CONTAINER,
        OPENJDK_11_CONTAINER,
        OPENJDK_17_CONTAINER,
        OPENJDK_DEVEL_11_CONTAINER,
        OPENJDK_DEVEL_17_CONTAINER,
        PYTHON36_CONTAINER,
        PYTHON310_CONTAINER,
        RUBY_25_CONTAINER,
        CONTAINER_389DS,
        DISTRIBUTION_CONTAINER,
    ]
    + GOLANG_CONTAINERS
    + RUST_CONTAINERS
    + POSTGRESQL_CONTAINERS
)

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
