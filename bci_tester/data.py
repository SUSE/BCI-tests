import os
from typing import List
from typing import Literal
from typing import Optional
from typing import Sequence

import pytest
from _pytest.mark.structures import MarkDecorator
from _pytest.mark.structures import ParameterSet
from pytest_container import DerivedContainer
from pytest_container.runtime import LOCALHOST

from bci_tester.runtime_choice import DOCKER_SELECTED


#: The operating system version as present in /etc/os-release & various other
#: places
OS_VERSION = os.getenv("OS_VERSION", "15.3")

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

if TARGET not in ("obs", "ibs", "ibs-cr"):
    if BASEURL is None:
        raise ValueError(
            f"Unknown target {TARGET} specified and BASEURL is not set, cannot continue"
        )
else:
    _SLE_SP = f"sle-{OS_MAJOR_VERSION}-sp{OS_SP_VERSION}"
    BASEURL = {
        "obs": f"registry.opensuse.org/devel/bci/{_SLE_SP}",
        "ibs": f"registry.suse.de/suse/{_SLE_SP}/update/bci",
        "ibs-cr": f"registry.suse.de/suse/{_SLE_SP}/update/cr/totest",
    }[TARGET]


def _create_container_version_mark(
    available_versions=List[str],
) -> MarkDecorator:
    """Creates a pytest mark for a container that is only available for a
    certain SLE version.

    Args:

    available_versions: list of versions for which this container is
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


_IMAGE_TYPE_T = Literal["dockerfile", "kiwi", "hybrid"]


def _get_repository_name(image_type: _IMAGE_TYPE_T):
    if TARGET == "ibs-cr":
        return "images"

    if image_type == "dockerfile":
        return "containerfile"
    elif image_type == "kiwi":
        return "images"
    elif image_type == "hybrid":
        return "images" if OS_SP_VERSION == 3 else "containerfile"


def create_BCI(
    image_type: _IMAGE_TYPE_T,
    build_tag: str,
    available_versions: Optional[List[str]] = None,
    extra_marks: Optional[Sequence[MarkDecorator]] = None,
    **kwargs,
) -> ParameterSet:
    """Creates a DerivedContainer wrapped in a pytest.param for the BCI with the
    given ``build_tag``.

    Args:
        image_type: define whether this image is build from a :file:`Dockerfile`
            or :file:`kiwi.xml` or both (depending on the service pack version)
        build_tag: the main build tag set for this image (it can be found at the
            top of the :file:`Dockerfile` or :file:`kiwi.xml`)
        available_versions: an optional list of operating system versions, for
            which this container image is available. Use this for container
            images that were not part of SLE 15 SP3.
        extra_marks: an optional sequence of marks that should be applied to
            this container image (e.g. to skip it on certain architectures)
        **kwargs: additional keyword arguments are forwarded to the constructor
            of the :py:class:`~pytest_container.DerivedContainer`
    """
    marks = [pytest.mark.__getattr__(build_tag.replace(":", "_"))]
    if extra_marks:
        for m in extra_marks:
            marks.append(m)

    if available_versions is not None:
        marks.append(_create_container_version_mark(available_versions))

    return pytest.param(
        DerivedContainer(
            base=f"{BASEURL}/{_get_repository_name(image_type)}/{build_tag}",
            containerfile=_BCI_CONTAINERFILE,
            **kwargs,
        ),
        marks=marks,
    )


BASE_CONTAINER = create_BCI(
    build_tag=f"bci/bci-base:{OS_VERSION}", image_type="kiwi"
)
MINIMAL_CONTAINER = create_BCI(
    build_tag=f"bci/bci-minimal:{OS_VERSION}", image_type="kiwi"
)
MICRO_CONTAINER = create_BCI(
    build_tag=f"bci/bci-micro:{OS_VERSION}", image_type="kiwi"
)

GO_1_16_CONTAINER = create_BCI(
    build_tag=f"bci/golang:1.16", image_type="hybrid"
)
GO_1_17_CONTAINER = create_BCI(
    build_tag=f"bci/golang:1.17", image_type="hybrid"
)
GO_1_18_CONTAINER = create_BCI(
    build_tag=f"bci/golang:1.18", image_type="hybrid"
)


OPENJDK_11_CONTAINER = create_BCI(
    build_tag=f"bci/openjdk:11", image_type="hybrid"
)
OPENJDK_DEVEL_11_CONTAINER = create_BCI(
    build_tag=f"bci/openjdk-devel:11", image_type="hybrid"
)
OPENJDK_17_CONTAINER = create_BCI(
    build_tag=f"bci/openjdk:17",
    image_type="dockerfile",
    available_versions=["15.4"],
)
OPENJDK_DEVEL_17_CONTAINER = create_BCI(
    build_tag=f"bci/openjdk-devel:17",
    image_type="dockerfile",
    available_versions=["15.4"],
)
NODEJS_12_CONTAINER = create_BCI(
    build_tag=f"bci/nodejs:12", image_type="kiwi", available_versions=["15.3"]
)
NODEJS_14_CONTAINER = create_BCI(
    build_tag=f"bci/nodejs:14", image_type="hybrid"
)
NODEJS_16_CONTAINER = create_BCI(
    build_tag=f"bci/nodejs:16", image_type="hybrid"
)

PYTHON36_CONTAINER = create_BCI(
    build_tag=f"bci/python:3.6", image_type="hybrid"
)
PYTHON39_CONTAINER = create_BCI(
    build_tag=f"bci/python:3.9", available_versions=["15.3"], image_type="kiwi"
)
PYTHON310_CONTAINER = create_BCI(
    build_tag=f"bci/python:3.10",
    available_versions=["15.4"],
    image_type="dockerfile",
)


RUBY_25_CONTAINER = create_BCI(build_tag=f"bci/ruby:2.5", image_type="hybrid")

_DOTNET_SKIP_ARCH_MARK = pytest.mark.skipif(
    LOCALHOST.system_info.arch != "x86_64",
    reason="The .Net containers are only available on x86_64",
)

DOTNET_SDK_3_1_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-sdk:3.1",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_5_0_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-sdk:5.0",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_SDK_6_0_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-sdk:6.0",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)

DOTNET_ASPNET_3_1_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-aspnet:3.1",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_5_0_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-aspnet:5.0",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_ASPNET_6_0_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-aspnet:6.0",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)

DOTNET_RUNTIME_3_1_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-runtime:3.1",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_5_0_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-runtime:5.0",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)
DOTNET_RUNTIME_6_0_CONTAINER = create_BCI(
    build_tag=f"bci/dotnet-runtime:6.0",
    image_type="dockerfile",
    extra_marks=(_DOTNET_SKIP_ARCH_MARK,),
)

INIT_CONTAINER = create_BCI(
    build_tag=f"bci/bci-init:{OS_VERSION}",
    image_type="hybrid",
    extra_launch_args=[
        "--privileged",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/run",
        "-v",
        "/sys/fs/cgroup:/sys/fs/cgroup:ro,z",
        "-e",
        "container=docker",
    ]
    if DOCKER_SELECTED
    else [],
    default_entry_point=True,
)

CONTAINER_389DS = create_BCI(
    build_tag=f"suse/389-ds:2.0",
    image_type="dockerfile",
    available_versions=["15.4"],
    default_entry_point=True,
    healthcheck_timeout_ms=30 * 1000,
    extra_launch_args=["-p", "3389:3389"],
    extra_environment_variables={"SUFFIX_NAME": "dc=example,dc=com"},
    singleton=True,
)


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

DOTNET_CONTAINERS = [
    DOTNET_SDK_3_1_CONTAINER,
    DOTNET_SDK_5_0_CONTAINER,
    DOTNET_SDK_6_0_CONTAINER,
    DOTNET_ASPNET_3_1_CONTAINER,
    DOTNET_ASPNET_5_0_CONTAINER,
    DOTNET_ASPNET_6_0_CONTAINER,
    DOTNET_RUNTIME_3_1_CONTAINER,
    DOTNET_RUNTIME_5_0_CONTAINER,
    DOTNET_RUNTIME_6_0_CONTAINER,
]
CONTAINERS_WITH_ZYPPER = [
    BASE_CONTAINER,
    GO_1_16_CONTAINER,
    GO_1_17_CONTAINER,
    GO_1_18_CONTAINER,
    OPENJDK_11_CONTAINER,
    OPENJDK_DEVEL_11_CONTAINER,
    OPENJDK_17_CONTAINER,
    OPENJDK_DEVEL_17_CONTAINER,
    NODEJS_12_CONTAINER,
    NODEJS_14_CONTAINER,
    NODEJS_16_CONTAINER,
    PYTHON36_CONTAINER,
    PYTHON39_CONTAINER,
    PYTHON310_CONTAINER,
    RUBY_25_CONTAINER,
    INIT_CONTAINER,
    CONTAINER_389DS,
] + (DOTNET_CONTAINERS if LOCALHOST.system_info.arch == "x86_64" else [])

CONTAINERS_WITHOUT_ZYPPER = [
    MINIMAL_CONTAINER,
    MICRO_CONTAINER,
]

#: Containers that are directly pulled from registry.suse.de
ALL_CONTAINERS = CONTAINERS_WITH_ZYPPER + CONTAINERS_WITHOUT_ZYPPER
