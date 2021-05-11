import pytest
import testinfra


def test_jdk_version(container):
    assert "openjdk {}".format(
        container.version
    ) in container.connection.check_output("java --version")
