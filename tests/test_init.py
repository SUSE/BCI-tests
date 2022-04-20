"""This module contains the tests for the init container, the image with
systemd pre-installed.

"""
import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import INIT_CONTAINER
from bci_tester.runtime_choice import DOCKER_SELECTED


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


@pytest.mark.parametrize(
    "container",
    [c for c in ALL_CONTAINERS if c != INIT_CONTAINER],
    indirect=True,
)
def test_systemd_not_installed_elsewhere(container):
    """Ensure that systemd is not present in all containers besides the init
    container.

    """
    assert not container.connection.exists("systemctl")

    # we cannot check for an existing package if rpm is not installed
    if container.connection.exists("rpm"):
        assert not container.connection.package("systemd").is_installed
