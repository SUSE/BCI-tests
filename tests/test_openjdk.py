import pytest
from bci_tester.data import OPENJDK_BASE_CONTAINER


@pytest.mark.parametrize(
    "container,java_version",
    [(OPENJDK_BASE_CONTAINER, "11")],
    indirect=["container"],
)
def test_jdk_version(container, java_version):
    assert f"openjdk {java_version}" in container.connection.check_output(
        "java --version"
    )

    assert (
        container.connection.check_output("echo $JAVA_VERSION") == java_version
    )
