"""This module contains the tests for the init container, the image with
systemd pre-installed.

"""
import pytest
from bci_tester.data import INIT_CONTAINER
from bci_tester.runtime_choice import DOCKER_SELECTED
from pytest_container.runtime import LOCALHOST


@pytest.mark.parametrize("container", [INIT_CONTAINER], indirect=True)
@pytest.mark.skipif(
    DOCKER_SELECTED
    and (int(LOCALHOST.package("systemd").version.split(".")[0]) >= 248),
    reason="Running systemd in docker is broken as of systemd 248, see https://github.com/moby/moby/issues/42275",
)
def test_systemd_present(container):
    """Check that :command:`systemctl` is in ``$PATH``, that :command:`systemctl
    status` works and that :file:`/etc/machine-id` exists.

    This test is currently broken due to `moby/moby#42275
    <https://github.com/moby/moby/issues/42275>`_ with :command:`docker` and
    :command:`systemd` >= 248.

    """
    assert container.connection.exists("systemctl")
    assert container.connection.file("/etc/machine-id").exists
    assert container.connection.run_expect([0], "systemctl status")
