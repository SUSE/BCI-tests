import pytest
import testinfra


def test_go_version(container):
    assert container.version in container.connection.check_output("go version")


def test_kured(container):
    cmd = container.connection.run(
        """git clone https://github.com/weaveworks/kured.git &&
        cd kured &&
        make cmd/kured/kured
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0
