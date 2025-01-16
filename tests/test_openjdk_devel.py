"""Tests for the OpenJDK development container (the container including JDK and
JRE).

"""

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_17_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_21_CONTAINER
from bci_tester.data import OS_VERSION
from tests import test_openjdk

CONTAINER_TEST_DIR = "/tmp/"
HOST_TEST_DIR = "tests/trainers/java/"

CONTAINER_IMAGES = [
    OPENJDK_DEVEL_11_CONTAINER,
    OPENJDK_DEVEL_17_CONTAINER,
    OPENJDK_DEVEL_21_CONTAINER,
]

DOCKERF_EXTENDED = f"""
WORKDIR {CONTAINER_TEST_DIR}
COPY {HOST_TEST_DIR} {CONTAINER_TEST_DIR}
ENTRYPOINT ["/bin/bash"]
"""

CONTAINER_IMAGES_EXTENDED = [
    DerivedContainer(
        base=container,
        containerfile=DOCKERF_EXTENDED,
    )
    for container in CONTAINER_IMAGES
]

CONTAINER_IMAGES_WITH_VERSION = [
    pytest.param(container, version, marks=container.marks)
    for container, version in zip(CONTAINER_IMAGES, ("11", "17", "21"))
]


def test_java_home(auto_container: ContainerData):
    """performs the same action as
    :py:func:`~tests.test_openjdk.test_java_home`.

    """
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
        container.connection.check_output("echo $JAVA_VERSION") == java_version
    )


def test_maven_present(auto_container):
    """Check that :command:`maven` is installed and successfully outputs its version
    via :command:`maven --version`.

    """
    assert auto_container.connection.run_expect([0], "mvn --version")


@pytest.mark.skipif(
    OS_VERSION not in ("15.3", "15.4", "15.5", "15.6"),
    reason="jshell is no longer the CMD as of SP7",
)
@pytest.mark.parametrize(
    "container,java_version",
    # Softfailure for bsc#1221983 only applies to OpenJDK-devel-21
    [
        param
        if param.values[1] != 21
        else pytest.param(
            *param.values,
            id=param.id,
            marks=param.marks
            + pytest.mark.xfail(
                condition=LOCALHOST.system_info.arch == "ppc64le",
                reason="https://bugzilla.suse.com/show_bug.cgi?id=1221983",
            ),
        )
        for param in CONTAINER_IMAGES_WITH_VERSION
    ],
    indirect=["container"],
)
def test_entrypoint(container, java_version, host, container_runtime):
    """Verify that the entry point of the OpenJDK devel container is the
    :command:`jshell`.

    """
    cmd = host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {container.image_url_or_id}",
    )
    # openjdk 17 prints the "jshell>" to stderr
    intro = cmd.stdout + cmd.stderr

    assert "jshell>" in intro
    assert f"Welcome to JShell -- Version {java_version}" in intro


@pytest.mark.parametrize(
    "container", CONTAINER_IMAGES_EXTENDED, indirect=["container"]
)
@pytest.mark.parametrize("java_file", ["Basic"])
def test_compile(container, java_file: str):
    """Verify that we can compile a simple java application successfully."""
    container.connection.check_output(
        f"ls {CONTAINER_TEST_DIR}{java_file}.java"
    )
    container.connection.check_output("javac --version")
    container.connection.check_output("java --version")
    container.connection.check_output(
        f"javac {CONTAINER_TEST_DIR}{java_file}.java"
    )
    container.connection.check_output(
        f"java -cp {CONTAINER_TEST_DIR} {java_file}"
    )


@pytest.mark.parametrize(
    "container",
    CONTAINER_IMAGES_EXTENDED,
    indirect=["container"],
)
def test_jdk_memory_error(container):
    """The purpose of this test is to verify two things: firstly,
    whether the flag that restricts memory usage (-Xmx) is working properly;
    and secondly, whether the Java test raises an OutOfMemoryError
    exception when the memory usage exceeds the set limit.
    """
    cmd = f"javac -Xlint:unchecked {CONTAINER_TEST_DIR}MemoryTest.java"
    testout = container.connection.run_expect([0], cmd)

    cmd = "java -Xmx10M MemoryTest"
    testout = container.connection.run_expect([1], cmd)

    assert "OutOfMemoryError" in testout.stderr
