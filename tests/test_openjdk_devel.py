"""Tests for the OpenJDK development container (the container including JDK and
JRE).

"""
import pytest
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param
from pytest_container.container import ContainerData

import tests.test_openjdk as test_openjdk
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_17_CONTAINER

CONTAINER_TEST_DIR = "/tmp/"
HOST_TEST_DIR = "tests/trainers/java/"

CONTAINER_IMAGES = [
    OPENJDK_DEVEL_11_CONTAINER,
    OPENJDK_DEVEL_17_CONTAINER,
]

DOCKERF_EXTENDED = f"""
WORKDIR {CONTAINER_TEST_DIR}
COPY {HOST_TEST_DIR} {CONTAINER_TEST_DIR}
"""

CONTAINER_IMAGES_EXTENDED = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(container),
            containerfile=DOCKERF_EXTENDED,
        ),
        marks=container.marks,
    )
    for container in CONTAINER_IMAGES
]

CONTAINER_IMAGES_WITH_VERSION = [
    pytest.param(container, version, marks=container.marks)
    for container, version in zip(CONTAINER_IMAGES, ("11", "17"))
]


def test_java_home(auto_container: ContainerData):
    test_openjdk.test_java_home(auto_container)


@pytest.mark.parametrize(
    "container,java_version",
    CONTAINER_IMAGES_WITH_VERSION,
    indirect=["container"],
)
def test_jdk_version(container, java_version: str):
    """Ensure that the environment variable ``JAVA_VERSION`` equals the output
    of :command:`javac --version` and :command:`java --version`

    """
    assert f"javac {java_version}" in container.connection.check_output(
        "javac -version"
    )
    assert java_version == container.connection.check_output(
        "echo $JAVA_VERSION"
    )

    assert f"openjdk {java_version}" in container.connection.check_output(
        "java --version"
    )

    assert (
        container.connection.run_expect(
            [0], "echo $JAVA_VERSION"
        ).stdout.strip()
        == java_version
    )


def test_maven_present(auto_container):
    """Check that :command:`maven` is installed and successfully outputs its version
    via :command:`maven --version`.

    """
    assert auto_container.connection.run_expect([0], "mvn --version")


@pytest.mark.parametrize(
    "container,java_version",
    CONTAINER_IMAGES_WITH_VERSION,
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


@pytest.mark.parametrize(
    "container", CONTAINER_IMAGES_EXTENDED, indirect=["container"]
)
@pytest.mark.parametrize("java_file", ["Basic"])
def test_compile(container, java_file: str):
    """Verify that the entry point of the OpenJDK devel container is the
    :command:`jshell`.

    """
    container.connection.run_expect(
        [0],
        f"ls {CONTAINER_TEST_DIR}{java_file}.java",
    )
    container.connection.run_expect(
        [0],
        "javac --version",
    )
    container.connection.run_expect(
        [0],
        "java --version",
    )
    container.connection.run_expect(
        [0],
        f"javac {CONTAINER_TEST_DIR}{java_file}.java",
    )
    container.connection.run_expect(
        [0],
        f"java -cp {CONTAINER_TEST_DIR} {java_file}",
    )
