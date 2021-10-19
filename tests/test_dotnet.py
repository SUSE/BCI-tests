"""Tests for the .Net container based on SLE with the rpms build from
Microsoft's binaries.

"""
import re

import pytest
from bci_tester.data import DOTNET_ARCH_SKIP_MARK
from bci_tester.data import DOTNET_ASPNET_3_1_BASE_CONTAINER
from bci_tester.data import DOTNET_ASPNET_5_0_BASE_CONTAINER
from bci_tester.data import DOTNET_SDK_3_1_BASE_CONTAINER
from bci_tester.data import DOTNET_SDK_5_0_BASE_CONTAINER
from pytest_container import GitRepositoryBuild


CONTAINER_IMAGES = [
    DOTNET_SDK_3_1_BASE_CONTAINER,
    DOTNET_SDK_5_0_BASE_CONTAINER,
]

pytestmark = DOTNET_ARCH_SKIP_MARK


@pytest.mark.parametrize(
    "container,sdk_version",
    [
        (DOTNET_SDK_3_1_BASE_CONTAINER, "3.1"),
        (DOTNET_SDK_5_0_BASE_CONTAINER, "5.0"),
    ],
    indirect=["container"],
)
def test_dotnet_sdk_version(container, sdk_version):
    """Ensure that the .Net SDKs and runtimes have the expected version."""
    assert (
        container.connection.check_output("dotnet --list-sdks")[:3]
        == sdk_version
    )
    runtimes = container.connection.check_output("dotnet --list-runtimes")
    assert ("Microsoft.AspNetCore.App " + sdk_version) in runtimes
    assert ("Microsoft.NETCore.App " + sdk_version) in runtimes


@pytest.mark.parametrize(
    "container,sdk_version",
    [
        (DOTNET_ASPNET_3_1_BASE_CONTAINER, "3.1"),
        (DOTNET_ASPNET_5_0_BASE_CONTAINER, "5.0"),
    ],
    indirect=["container"],
)
def test_dotnet_aspnet_version(container, sdk_version):
    """Checks for the ASP.Net containers:

    - Ensure that no .Net SDKs are present in the container
    - Ensure that the runtimes have the expected version
    """
    assert container.connection.check_output("dotnet --list-sdks") == ""
    runtimes = container.connection.check_output("dotnet --list-runtimes")
    assert ("Microsoft.AspNetCore.App " + sdk_version) in runtimes
    assert ("Microsoft.NETCore.App " + sdk_version) in runtimes


@pytest.mark.parametrize(
    "container_per_test",
    [
        DOTNET_SDK_3_1_BASE_CONTAINER,
        DOTNET_SDK_5_0_BASE_CONTAINER,
    ],
    indirect=True,
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
        container_per_test.connection.run_expect(
            [0], "cd MyApp && dotnet run"
        ).stdout.strip()
        == "Hello World!"
    )


@pytest.mark.parametrize(
    "container_per_test",
    [DOTNET_SDK_5_0_BASE_CONTAINER],
    indirect=["container_per_test"],
)
@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/nopSolutions/nopCommerce.git",
            repository_tag="release-4.40.4",
            build_command="""dotnet build ./src/NopCommerce.sln &&
dotnet test ./src/Tests/Nop.Tests/Nop.Tests.csproj""",
        )
    ],
    indirect=["container_git_clone"],
)
def test_popular_web_apps(container_per_test, container_git_clone):
    """Test the build of a popular web application:

    - Build `nopCommerce <https://github.com/nopSolutions/nopCommerce.git>`_
      release ``4.40.4`` via :command:`dotnet build ./src/NopCommerce.sln &&
      dotnet test ./src/Tests/Nop.Tests/Nop.Tests.csproj`

    """
    container_per_test.connection.run_expect(
        [0], container_git_clone.test_command
    )


@pytest.mark.parametrize(
    "container_per_test",
    [
        DOTNET_SDK_3_1_BASE_CONTAINER,
        DOTNET_SDK_5_0_BASE_CONTAINER,
    ],
    indirect=True,
)
def test_dotnet_sdk_telemetry_deactivated(container_per_test):
    """Test that telemetry of the .Net SDK is turned off by default.

    The .Net SDK will by default have `telemetry
    <https://docs.microsoft.com/en-us/dotnet/core/tools/telemetry>`_ enabled. We
    disable it via an environment variable and check that the no telemetry
    notice is present in the output of :command:`dotnet help`.

    """
    dotnet_new_stdout = container_per_test.connection.run_expect(
        [0], "dotnet help"
    ).stdout.strip()
    assert not re.search(r"telemetry", dotnet_new_stdout, re.IGNORECASE)
