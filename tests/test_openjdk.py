"""Tests of the OpenJDK base container."""
import pytest

from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER


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
