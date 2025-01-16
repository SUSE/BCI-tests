"""Tests for the .Net container based on SLE with the rpms build from
Microsoft's binaries.

"""

import re
import xml.etree.ElementTree as ET
from typing import List
from typing import Tuple

import pytest
from _pytest.mark import ParameterSet
from pytest_container import DerivedContainer
from pytest_container import GitRepositoryBuild

from bci_tester.data import DOTNET_ASPNET_8_0_CONTAINER
from bci_tester.data import DOTNET_ASPNET_9_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_8_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_9_0_CONTAINER
from bci_tester.data import DOTNET_SDK_8_0_CONTAINER
from bci_tester.data import DOTNET_SDK_9_0_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.util import get_repos_from_connection

DOTNET_SDK_CONTAINERS = [
    DOTNET_SDK_8_0_CONTAINER,
    DOTNET_SDK_9_0_CONTAINER,
]

#: Name and alias of the microsoft .Net repository
MS_REPO_NAME = "packages-microsoft-com-prod"

pytestmark = pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="no Tumbleweed dotnet containers",
)


def _generate_ctr_ver_param(
    ctr_ver: Tuple[DerivedContainer, str],
) -> ParameterSet:
    """Converts a `(Container, Version)` tuple into a `pytest.param` that
    contains the exact same values but has the marks of the container.

    """
    return pytest.param(ctr_ver[0], ctr_ver[1], marks=ctr_ver[0].marks)


@pytest.mark.parametrize(
    "container,sdk_version",
    map(
        _generate_ctr_ver_param,
        (
            (DOTNET_SDK_8_0_CONTAINER, "8.0"),
            (DOTNET_SDK_9_0_CONTAINER, "9.0"),
        ),
    ),
    indirect=["container"],
)
def test_dotnet_sdk_version(container, sdk_version):
    """Ensure that the .Net SDKs and runtimes have the expected version."""
    assert (
        container.connection.check_output("dotnet --list-sdks")[:3]
        == sdk_version
    )
    runtimes = container.connection.check_output("dotnet --list-runtimes")
    assert "Microsoft.AspNetCore.App " + sdk_version in runtimes
    assert "Microsoft.NETCore.App " + sdk_version in runtimes


@pytest.mark.parametrize(
    "container,runtime_version",
    map(
        _generate_ctr_ver_param,
        (
            (DOTNET_ASPNET_8_0_CONTAINER, "8.0"),
            (DOTNET_ASPNET_9_0_CONTAINER, "9.0"),
        ),
    ),
    indirect=["container"],
)
def test_dotnet_aspnet_runtime_versions(container, runtime_version):
    """Checks for the ASP.Net containers:

    - Ensure that no .Net SDKs are present in the container
    - Ensure that the runtimes have the expected version
    - Ensure that the .Net and ASP.Net runtimes are present
    """
    assert container.connection.check_output("dotnet --list-sdks") == ""
    runtimes = container.connection.check_output("dotnet --list-runtimes")
    assert "Microsoft.AspNetCore.App " + runtime_version in runtimes
    assert "Microsoft.NETCore.App " + runtime_version in runtimes


@pytest.mark.parametrize(
    "container,runtime_version",
    map(
        _generate_ctr_ver_param,
        (
            (DOTNET_RUNTIME_8_0_CONTAINER, "8.0"),
            (DOTNET_RUNTIME_9_0_CONTAINER, "9.0"),
        ),
    ),
    indirect=["container"],
)
def test_dotnet_runtime_present(container, runtime_version):
    """Verify that there is one .Net runtime present in the .Net runtime only container."""
    runtimes = (
        container.connection.run_expect([0], "dotnet --list-runtimes")
        .stdout.strip()
        .split("\n")
    )
    assert len(runtimes) == 1
    assert "Microsoft.NETCore.App " + runtime_version in runtimes[0]


@pytest.mark.parametrize(
    "container_per_test",
    DOTNET_SDK_CONTAINERS,
    indirect=["container_per_test"],
)
def test_dotnet_hello_world(container_per_test):
    """Test the build of a hello world .Net console application by running:

    - :command:`dotnet new console -o MyApp`
    - :command:`cd MyApp && dotnet run` and checking that it outputs ``Hello
      World!``
    """
    container_per_test.connection.run_expect(
        [0], "dotnet new console -o MyApp"
    )
    assert (
        container_per_test.connection.check_output("cd MyApp && dotnet run")
        .strip()
        .endswith("Hello, World!")
    )


@pytest.mark.parametrize(
    "container_per_test",
    [DOTNET_SDK_8_0_CONTAINER],
    indirect=["container_per_test"],
)
@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/nopSolutions/nopCommerce.git",
            repository_tag="release-4.70.0",
            build_command="dotnet build ./src/NopCommerce.sln",
        )
    ],
    indirect=["container_git_clone"],
)
def test_popular_web_apps(container_per_test, container_git_clone):
    """Test the build of a popular web application:

    - Build `nopCommerce <https://github.com/nopSolutions/nopCommerce.git>`_
      release ``4.70.0`` via :command:`dotnet build ./src/NopCommerce.sln`

    """
    container_per_test.connection.check_output(
        container_git_clone.test_command
    )


@pytest.mark.parametrize(
    "container_per_test",
    DOTNET_SDK_CONTAINERS,
    indirect=True,
)
def test_dotnet_sdk_telemetry_deactivated(container_per_test):
    """Test whether telemetry of the .Net SDK is off by default.

    The .Net SDK will by default have `telemetry
    <https://docs.microsoft.com/en-us/dotnet/core/tools/telemetry>`_ enabled. We
    disable it via an environment variable and check that the no telemetry
    notice is present in the output of :command:`dotnet help`.

    """
    dotnet_new_stdout = container_per_test.connection.check_output(
        "dotnet help"
    )
    assert not re.search(r"telemetry", dotnet_new_stdout, re.IGNORECASE)


@pytest.mark.parametrize(
    "container_per_test", DOTNET_SDK_CONTAINERS, indirect=True
)
def test_microsoft_dotnet_repository(container_per_test):
    """Check that we have configured the Microsoft .Net
    repository.

    The following checks are run:

    1. A repository with the alias and name :py:const:`MS_REPO_NAME` exists, is
       enabled and ``gpgcheck`` is enabled as well.
    2. The repository contains at least one package
    3. Only packages starting with ``dotnet``, ``aspnet`` or
       ``netstandard-targeting-pack`` are installed from that repository
    """

    def get_pkg_list(extra_search_flags: str = "") -> List[str]:
        zypper_xml_out = ET.fromstring(
            container_per_test.connection.check_output(
                f"zypper -x se {extra_search_flags} -r {MS_REPO_NAME}"
            )
        )
        solvable_list = list(
            [
                child
                for child in zypper_xml_out
                if child.tag == "search-result"
            ][0]
        )
        assert len(solvable_list) == 1
        pkg_names = [
            pkg.get("name")
            for pkg in solvable_list[0]
            if pkg.tag == "solvable" and pkg.get("kind") == "package"
        ]
        valid_names = [pkg_name for pkg_name in pkg_names if pkg_name]
        assert len(pkg_names) == len(valid_names)
        return valid_names

    repos = get_repos_from_connection(container_per_test.connection)
    assert len(repos) >= 2, (
        "The .Net containers must contain the SLE_BCI and MS .Net repository"
    )

    ms_repos = [repo for repo in repos if repo.name == MS_REPO_NAME]
    assert len(ms_repos) == 1
    ms_repo = ms_repos[0]

    assert ms_repo.alias == MS_REPO_NAME
    assert ms_repo.url == "https://packages.microsoft.com/sles/15/prod/"
    assert ms_repo.enabled
    assert ms_repo.gpgcheck

    assert len(get_pkg_list()) > 0
    for pkg_name in get_pkg_list("-i"):
        assert (
            pkg_name[:6] == "dotnet"
            or pkg_name[:6] == "aspnet"
            or pkg_name[:27] == "netstandard-targeting-pack-"
        )
