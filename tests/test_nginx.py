"""This module contains the tests for the nginx container, the image with nginx pre-installed."""

import pytest
import requests
from pytest_container import DerivedContainer
from pytest_container.container import ContainerLauncher
from pytest_container.runtime import OciRuntimeBase
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import NGINX_CONTAINERS

CONTAINER_IMAGES = NGINX_CONTAINERS

USERS = [
    "root",
    "nginx",
    0,
    101,
    499,
    999,
    1000,
    1001,
    10001,
    65534,
]


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
)
def check_nginx_response(host_port: int):
    resp = requests.get(f"http://0.0.0.0:{host_port}/", timeout=30)
    resp.raise_for_status()
    assert "Welcome to nginx" in resp.text


@pytest.mark.parametrize("ctr_image", NGINX_CONTAINERS)
@pytest.mark.parametrize("user", USERS)
def test_nginx_welcome_page(
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
    user: tuple[int | str],
):
    """
    Test that the default welcome page is served by the container
    independent of which user is executing the container.

    Ensure that the user inside the container matches the UID/username
    defined in the container run command.
    """

    with ContainerLauncher.from_pytestconfig(
        ctr_image, container_runtime, pytestconfig
    ) as launcher:
        launcher.extra_run_args.append(f"--user={user}")
        launcher.launch_container()
        con = launcher.container_data.connection

        if isinstance(user, str):
            assert con.run_expect([0], "id -u -n").stdout.strip() == user
        else:
            assert con.run_expect([0], "id -u").stdout.strip() == str(user)

        if user in [0, "root"]:
            # port 80 mapping
            host_port = launcher.container_data.forwarded_ports[0].host_port
        else:
            # port 8080 mapping
            host_port = launcher.container_data.forwarded_ports[1].host_port

        check_nginx_response(host_port)
