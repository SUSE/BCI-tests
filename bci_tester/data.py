import os
from typing import List
from typing import Union

import pytest
from _pytest.mark.structures import MarkDecorator
from _pytest.mark.structures import ParameterSet
from bci_tester.runtime_choice import DOCKER_SELECTED
from pytest_container import Container
from pytest_container import DerivedContainer
from pytest_container.runtime import LOCALHOST


ContainerT = Union[Container, DerivedContainer, ParameterSet]


DEFAULT_REGISTRY = "registry.suse.de"

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

#: the base URL under which all containers can be found on registry.suse.de
BASEURL = os.getenv(
    "BASEURL",
    f"{DEFAULT_REGISTRY}/suse/sle-{OS_MAJOR_VERSION}-sp{OS_SP_VERSION}/update/cr/totest/images",
)


def create_container_version_mark(
    available_versions=List[str],
) -> MarkDecorator:
    """Creates a pytest mark for a container that is only available for a
    certain SLE version.

    Parameters:

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


BASE_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/suse/sle15:{OS_VERSION}",
)
MINIMAL_CONTAINER: Union[Container, ParameterSet] = Container(
    url=f"{BASEURL}/bci/bci-minimal:{OS_VERSION}",
)
MICRO_CONTAINER: Union[Container, ParameterSet] = Container(
    url=f"{BASEURL}/bci/bci-micro:{OS_VERSION}"
)

GO_1_16_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/golang:1.16")
GO_1_17_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/golang:1.17")

OPENJDK_11_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/openjdk:11")
OPENJDK_DEVEL_11_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/openjdk-devel:11"
)
NODEJS_12_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/nodejs:12")
NODEJS_14_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/nodejs:14")

PYTHON36_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/python:3.6")
PYTHON39_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/python:3.9")

RUBY_25_CONTAINER: ContainerT = Container(url=f"{BASEURL}/bci/ruby:2.5")

DOTNET_SDK_3_1_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-sdk:3.1",
)
DOTNET_SDK_5_0_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-sdk:5.0",
)
DOTNET_SDK_6_0_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-sdk:6.0",
)

DOTNET_ASPNET_3_1_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-aspnet:3.1",
)
DOTNET_ASPNET_5_0_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-aspnet:5.0",
)
DOTNET_ASPNET_6_0_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-aspnet:6.0",
)

DOTNET_RUNTIME_3_1_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-runtime:3.1"
)
DOTNET_RUNTIME_5_0_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-runtime:5.0"
)
DOTNET_RUNTIME_6_0_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/dotnet-runtime:6.0"
)

INIT_CONTAINER: ContainerT = Container(
    url=f"{BASEURL}/bci/bci-init:{OS_VERSION}",
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

CONTAINER_389DS = Container(
    url=f"{BASEURL}/suse/389-ds:1.4",
    default_entry_point=True,
    healthcheck_timeout_ms=30 * 1000,
    extra_launch_args=["-p", "3389:3389"],
    extra_environment_variables={"SUFFIX_NAME": "dc=example,dc=com"},
    singleton=True,
)


#
# !! IMPORTANT !!
# ===============
#
# All "base" containers which get pre-configured with the SLE_BCI repository
# should be put into this if branch so that their repository gets replaced on
# setting the `BCI_DEVEL_REPO` environment variable.
#
# We must not run any zypper commands here, as otherwise container-suseconnect
# will keep a ton of metadata of the fetched repositories (which is a lot on
# registered systems)
#
BCI_DEVEL_REPO = os.getenv("BCI_DEVEL_REPO")
if BCI_DEVEL_REPO is None:
    BCI_DEVEL_REPO = f"https://updates.suse.com/SUSE/Products/SLE-BCI/{OS_MAJOR_VERSION}-SP{OS_SP_VERSION}/{LOCALHOST.system_info.arch}/product/"
else:
    REPLACE_REPO_CONTAINERFILE = f"RUN sed -i 's|baseurl.*|baseurl={BCI_DEVEL_REPO}|' /etc/zypp/repos.d/SLE_BCI.repo"

    (
        BASE_CONTAINER,
        GO_1_16_CONTAINER,
        GO_1_17_CONTAINER,
        OPENJDK_11_CONTAINER,
        OPENJDK_DEVEL_11_CONTAINER,
        NODEJS_12_CONTAINER,
        NODEJS_14_CONTAINER,
        PYTHON36_CONTAINER,
        PYTHON39_CONTAINER,
        RUBY_25_CONTAINER,
        DOTNET_SDK_3_1_CONTAINER,
        DOTNET_SDK_5_0_CONTAINER,
        DOTNET_SDK_6_0_CONTAINER,
        DOTNET_ASPNET_3_1_CONTAINER,
        DOTNET_ASPNET_5_0_CONTAINER,
        DOTNET_ASPNET_6_0_CONTAINER,
        DOTNET_RUNTIME_3_1_CONTAINER,
        DOTNET_RUNTIME_5_0_CONTAINER,
        DOTNET_RUNTIME_6_0_CONTAINER,
        INIT_CONTAINER,
        CONTAINER_389DS,
    ) = (
        DerivedContainer(
            base=cont.url,
            containerfile=REPLACE_REPO_CONTAINERFILE,
            **{k: v for (k, v) in cont.__dict__.items() if k != "url"},
        )
        for cont in (
            BASE_CONTAINER,
            GO_1_16_CONTAINER,
            GO_1_17_CONTAINER,
            OPENJDK_11_CONTAINER,
            OPENJDK_DEVEL_11_CONTAINER,
            NODEJS_12_CONTAINER,
            NODEJS_14_CONTAINER,
            PYTHON36_CONTAINER,
            PYTHON39_CONTAINER,
            RUBY_25_CONTAINER,
            DOTNET_SDK_3_1_CONTAINER,
            DOTNET_SDK_5_0_CONTAINER,
            DOTNET_SDK_6_0_CONTAINER,
            DOTNET_ASPNET_3_1_CONTAINER,
            DOTNET_ASPNET_5_0_CONTAINER,
            DOTNET_ASPNET_6_0_CONTAINER,
            DOTNET_RUNTIME_3_1_CONTAINER,
            DOTNET_RUNTIME_5_0_CONTAINER,
            DOTNET_RUNTIME_6_0_CONTAINER,
            INIT_CONTAINER,
            CONTAINER_389DS,
        )
    )


PYTHON39_CONTAINER = pytest.param(
    PYTHON39_CONTAINER, marks=create_container_version_mark(["15.3"])
)
CONTAINER_389DS = pytest.param(
    CONTAINER_389DS, marks=create_container_version_mark(["15.4"])
)

(
    DOTNET_SDK_3_1_CONTAINER,
    DOTNET_SDK_5_0_CONTAINER,
    DOTNET_SDK_6_0_CONTAINER,
    DOTNET_ASPNET_3_1_CONTAINER,
    DOTNET_ASPNET_5_0_CONTAINER,
    DOTNET_ASPNET_6_0_CONTAINER,
    DOTNET_RUNTIME_3_1_CONTAINER,
    DOTNET_RUNTIME_5_0_CONTAINER,
    DOTNET_RUNTIME_6_0_CONTAINER,
) = (
    pytest.param(
        cont,
        marks=(
            pytest.mark.skipif(
                LOCALHOST.system_info.arch != "x86_64",
                reason="The .Net containers are only available on x86_64",
            ),
        ),
    )
    for cont in (
        DOTNET_SDK_3_1_CONTAINER,
        DOTNET_SDK_5_0_CONTAINER,
        DOTNET_SDK_6_0_CONTAINER,
        DOTNET_ASPNET_3_1_CONTAINER,
        DOTNET_ASPNET_5_0_CONTAINER,
        DOTNET_ASPNET_6_0_CONTAINER,
        DOTNET_RUNTIME_3_1_CONTAINER,
        DOTNET_RUNTIME_5_0_CONTAINER,
        DOTNET_RUNTIME_6_0_CONTAINER,
    )
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
    OPENJDK_11_CONTAINER,
    OPENJDK_DEVEL_11_CONTAINER,
    NODEJS_12_CONTAINER,
    NODEJS_14_CONTAINER,
    PYTHON36_CONTAINER,
    PYTHON39_CONTAINER,
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
