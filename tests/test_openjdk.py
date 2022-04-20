"""Tests of the OpenJDK base container."""
import pytest

from bci_tester.data import OPENJDK_11_CONTAINER


@pytest.mark.parametrize(
    "container,java_version",
    [(OPENJDK_11_CONTAINER, "11")],
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
