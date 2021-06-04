import pytest

from bci_tester.parse_data import containers


def get_init_container():
    init_type_containers = [c for c in containers if c.type == "init"]
    assert len(init_type_containers) == 1, (
        f"found {len(init_type_containers)} containers with the "
        "type 'init', but expected 1"
    )
    return init_type_containers[0]


INIT_CONTAINER = get_init_container()
INIT_CONTAINER.extra_launch_args = [
    "--privileged",
    # need to give the container access to dbus when invoking tox via sudo,
    # because then things get weird...
    # see:
    # https://askubuntu.com/questions/1297226/how-to-run-systemctl-command-inside-docker-container
    "-v",
    "/var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket",
]


@pytest.mark.parametrize("container", [INIT_CONTAINER], indirect=True)
def test_systemd_present(container):
    assert container.connection.exists("systemctl")
    assert container.connection.run_expect([0], "systemctl status")


@pytest.mark.parametrize("container", [INIT_CONTAINER], indirect=True)
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
    "container", [c for c in containers if c.type != "init"], indirect=True
)
def test_systemd_not_installed_elsewhere(container):
    assert not container.connection.package("systemd").is_installed
