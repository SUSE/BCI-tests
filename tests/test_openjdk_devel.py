"""Tests for the OpenJDK development container (the container including JDK and
JRE).

"""
import pytest

from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER


CONTAINER_IMAGES = [OPENJDK_DEVEL_11_CONTAINER]


@pytest.mark.parametrize(
    "container,java_version",
    [(OPENJDK_DEVEL_11_CONTAINER, "11")],
    indirect=["container"],
)
def test_jdk_version(container, java_version):
    """Ensure that the environment variable ``JAVA_VERSION`` equals the output of
    :command:`javac --version`.

    """
    assert f"javac {java_version}" in container.connection.check_output(
        "javac -version"
    )
    assert java_version == container.connection.check_output(
        "echo $JAVA_VERSION"
    )


def test_maven_present(auto_container):
    """Check that :command:`maven` is installed and successfully outputs its version
    via :command:`maven --version`.

    """
    assert auto_container.connection.run_expect([0], "mvn --version")


@pytest.mark.parametrize(
    "container,java_version",
    [(OPENJDK_DEVEL_11_CONTAINER, "11")],
    indirect=["container"],
)
def test_entrypoint(container, java_version, host, container_runtime):
    """Verify that the entry point of the OpenJDK devel container is the
    :command:`jshell`.

    """
    intro = host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {container.image_url_or_id}",
    ).stdout

    assert "jshell>" in intro
    assert f"Welcome to JShell -- Version {java_version}" in intro
