import pytest
from bci_tester.parse_data import containers


def test_jdk_version(auto_container):
    assert (
        f"javac {auto_container.version}"
        in auto_container.connection.check_output("javac -version")
    )
    assert auto_container.version == auto_container.connection.check_output(
        "echo $JAVA_VERSION"
    )


def test_maven_present(auto_container):
    assert auto_container.connection.run_expect([0], "mvn --version")


OPENJDK_DEVEL_CONTAINERS = [
    (container.url, container.version)
    for container in containers
    if container.type == "openjdk-devel"
]


@pytest.mark.parametrize(
    "devel_container",
    OPENJDK_DEVEL_CONTAINERS,
)
def test_entrypoint(devel_container, host, container_runtime):
    intro = host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {devel_container[0]}",
    ).stdout

    assert "jshell>" in intro
    assert f"Welcome to JShell -- Version {devel_container[1]}" in intro
