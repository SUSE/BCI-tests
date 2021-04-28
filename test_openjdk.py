import pytest
import testinfra


def test_jdk_version(container):
    assert "openjdk {}".format(container.version) in container.connection.check_output(
        "java --version"
    )


def test_maven_present(container):
    assert container.connection.run_expect([0], "mvn --version")
