"""Tests of the OpenJDK base container."""
from typing import List

import pytest
from pytest_container import DerivedContainer
from pytest_container import OciRuntimeBase
from pytest_container.container import container_from_pytest_param

from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER

container_test_dir = "/tmp/"
host_test_dir = "tests/trainers/java/"

DOCKERF_EXTENDED = f"""
WORKDIR {container_test_dir}
COPY {host_test_dir} {container_test_dir}
"""

CONTAINER_IMAGES = [
    OPENJDK_11_CONTAINER,
    OPENJDK_17_CONTAINER,
]

CONTAINER_IMAGES_EXTENDED = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(container),
            containerfile=DOCKERF_EXTENDED,
        ),
        marks=container.marks,
        id=container.id,
    )
    for container in CONTAINER_IMAGES
]


@pytest.mark.parametrize(
    "container,java_version",
    [
        pytest.param(
            OPENJDK_11_CONTAINER, "11", marks=OPENJDK_11_CONTAINER.marks
        ),
        pytest.param(
            OPENJDK_17_CONTAINER, "17", marks=OPENJDK_17_CONTAINER.marks
        ),
    ],
    indirect=["container"],
)
def test_jdk_version(container, java_version):
    """Check that the environment variable ``JAVA_VERSION`` is equal to the output
    of :command:`java --version`.

    """
    assert f"openjdk {java_version}" in container.connection.check_output(
        "java --version"
    )

    assert (
        container.connection.check_output("echo $JAVA_VERSION") == java_version
    )


@pytest.mark.parametrize(
    "container_per_test",
    CONTAINER_IMAGES_EXTENDED,
    indirect=["container_per_test"],
)
@pytest.mark.parametrize(
    "test_to_run, expected_strings, expected_exit_status, java_params",
    [
        (
            "threads_concurrency_and_sleep",
            ["I am the thread 1", "I am the thread 2"],
            [0],
            "",
        ),
        ("time", ["All OK"], [0], ""),
        (
            "files_and_directories",
            ["All OK"],
            [0],
            "",
        ),
        (
            "memory",
            ["Iteration: (2)", "OutOfMemoryError"],
            [1],
            "-Xmx10M",
        ),
        ("garbage_collector", [], [0], ""),
    ],
)
def test_jdk_extended(
    container_per_test,
    test_to_run: str,
    expected_strings: List[str],
    expected_exit_status: List[int],
    java_params: str,
    host,
    container_runtime: OciRuntimeBase,
):
    """Executes a set of java files stored on test/trainers/java/ directory.
    It covers:
    - threading tests
    - java time and date tests
    - files and dirs tests
    - memory allocation
    - garbage collector
    The validation is done checking the exit code (0) and checking that some
    expected strings can be found on the stdout of the execution.
    """

    testout = container_per_test.connection.run_expect(
        expected_exit_status,
        "java "
        + java_params
        + " "
        + container_test_dir
        + test_to_run
        + ".java 2>&1",
    )

    for check in expected_strings:
        assert check in testout.stdout
