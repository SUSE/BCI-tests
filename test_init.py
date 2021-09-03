import pytest
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import INIT_CONTAINER
from bci_tester.helpers import get_selected_runtime


@pytest.mark.parametrize("container", [INIT_CONTAINER], indirect=True)
@pytest.mark.skip(reason="Needs to get fixed properly")
def test_systemd_present(container):
    assert container.connection.exists("systemctl")
    assert container.connection.run_expect([0], "systemctl status")


@pytest.mark.parametrize("container", [INIT_CONTAINER], indirect=True)
@pytest.mark.skipif(
    get_selected_runtime().runner_binary != "docker",
    reason="Docker in docker can only be tested when using the docker runtime",
)
@pytest.mark.skip(reason="Needs to get fixed properly")
def test_docker_in_docker(container):
    assert container.connection.run_expect([0], "zypper -n in docker")
    assert container.connection.run_expect([0], "systemctl start docker")
    assert container.connection.run_expect([0], "docker ps")
    assert container.connection.run_expect(
        [0],
        "docker run --rm registry.opensuse.org/opensuse/tumbleweed:latest "
        "/usr/bin/ls",
    )


@pytest.mark.parametrize(
    "container",
    [c for c in ALL_CONTAINERS if c != INIT_CONTAINER],
    indirect=True,
)
def test_systemd_not_installed_elsewhere(container):
    assert not container.connection.package("systemd").is_installed
