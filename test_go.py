import pytest
import testinfra


def test_go_version(container):
    assert container.version in container.connection.check_output("go version")
