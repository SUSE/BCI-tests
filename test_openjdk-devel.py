import pytest
from bci_tester.data import OPENJDK_DEVEL_BASE_CONTAINER


CONTAINER_IMAGES = [OPENJDK_DEVEL_BASE_CONTAINER]


@pytest.mark.parametrize(
    "container,java_version",
    [(OPENJDK_DEVEL_BASE_CONTAINER, "11")],
    indirect=["container"],
)
def test_jdk_version(container, java_version):
    assert f"javac {java_version}" in container.connection.check_output(
        "javac -version"
    )
    assert java_version == container.connection.check_output(
        "echo $JAVA_VERSION"
    )


def test_maven_present(auto_container):
    assert auto_container.connection.run_expect([0], "mvn --version")


@pytest.mark.parametrize(
    "container,java_version",
    [(OPENJDK_DEVEL_BASE_CONTAINER, "11")],
    indirect=["container"],
)
def test_entrypoint(container, java_version, host, container_runtime):
    intro = host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {container.image_url_or_id}",
    ).stdout

    assert "jshell>" in intro
    assert f"Welcome to JShell -- Version {java_version}" in intro
