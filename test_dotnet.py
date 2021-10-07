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
    assert container.connection.check_output("dotnet --list-sdks") == ""
    runtimes = container.connection.check_output("dotnet --list-runtimes")
    assert ("Microsoft.AspNetCore.App " + sdk_version) in runtimes
    assert ("Microsoft.NETCore.App " + sdk_version) in runtimes


@pytest.mark.parametrize(
    "container",
    [
        DOTNET_SDK_3_1_BASE_CONTAINER,
        DOTNET_SDK_5_0_BASE_CONTAINER,
    ],
    indirect=["container"],
)
def test_dotnet_hello_world(container):
    container.connection.run_expect([0], "dotnet new console -o MyApp")
    assert (
        container.connection.check_output("cd MyApp && dotnet run")
        == "Hello World!"
    )


@pytest.mark.parametrize(
    "container", [DOTNET_SDK_5_0_BASE_CONTAINER], indirect=["container"]
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
def test_popular_web_apps(container, container_git_clone):
    container.connection.run_expect([0], container_git_clone.test_command)


@pytest.mark.parametrize(
    "container",
    [
        DOTNET_SDK_3_1_BASE_CONTAINER,
        DOTNET_SDK_5_0_BASE_CONTAINER,
    ],
    indirect=["container"],
)
def test_dotnet_sdk_telemetry_deactivated(container):
    dotnet_new_stdout = container.connection.run_expect(
        [0], "dotnet help"
    ).stdout.strip()
    assert not re.search(r"telemetry", dotnet_new_stdout, re.IGNORECASE)
