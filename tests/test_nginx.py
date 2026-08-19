"""This module contains the tests for the nginx container, the image with nginx pre-installed."""

from pathlib import Path
from typing import Union

import pytest
import requests
from pytest_container.container import BindMount
from pytest_container.container import ContainerLauncher
from pytest_container.container import DerivedContainer
from pytest_container.container import ImageFormat
from pytest_container.container import PortForwarding
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.pod import Pod
from pytest_container.pod import PodData
from pytest_container.runtime import OciRuntimeBase
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import NGINX_CONTAINERS

CONTAINER_IMAGES = NGINX_CONTAINERS

NGINX_WITH_CUSTOM_CONF = []
for param in NGINX_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(param)
    NGINX_WITH_CUSTOM_CONF.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                volume_mounts=[
                    BindMount(
                        container_path="/etc/nginx/nginx.conf",
                        host_path=str(
                            Path(__file__).parent
                            / "files"
                            / "nginx"
                            / "nginx.non-root.conf"
                        ),
                    ),
                ],
                forwarded_ports=ctr.forwarded_ports,
            ),
            marks=marks,
            id=f"nginx-non-root from {ctr.baseurl}",
        )
    )


GUNICORN_HTTP_CONTAINER = DerivedContainer(
    container_id="gunicorn",
    base="registry.suse.com/bci/python",
    containerfile=(
        """
WORKDIR /app
COPY tests/files/nginx/app.py .
RUN pip install --no-cache-dir gunicorn
CMD gunicorn --bind 0.0.0.0:5000 app:app
"""
    ),
    forwarded_ports=[PortForwarding(container_port=5000)],
    image_format=ImageFormat.DOCKER,
)

GUNICORN_UWSGI_CONTAINER = DerivedContainer(
    container_id="gunicorn",
    base="registry.suse.com/bci/python",
    containerfile=(
        """
WORKDIR /app
COPY tests/files/nginx/app.py .
RUN pip install --no-cache-dir gunicorn
CMD gunicorn --protocol uwsgi --bind 0.0.0.0:5001 app:app
"""
    ),
    forwarded_ports=[PortForwarding(container_port=5001)],
    image_format=ImageFormat.DOCKER,
)

NGINX_PROXY_PODS = []

for ctr in NGINX_CONTAINERS:
    nginx_ctr, marks = container_and_marks_from_pytest_param(ctr)

    # pods are slower and gunicorn is configured to return a sizeable body
    # test only know users and a generic one
    for user in ["root", "nginx", "1001"]:
        pod = pytest.param(
            Pod(
                containers=[
                    DerivedContainer(
                        container_id=f"nginx-proxy from {nginx_ctr.baseurl}",
                        base=nginx_ctr,
                        volume_mounts=[
                            BindMount(
                                container_path="/etc/nginx/nginx.conf",
                                host_path=str(
                                    Path(__file__).parent
                                    / "files"
                                    / "nginx"
                                    / "nginx.proxy.conf"
                                ),
                            ),
                        ],
                        extra_launch_args=(["--user", user]),
                        forwarded_ports=nginx_ctr.forwarded_ports,
                    ),
                    GUNICORN_HTTP_CONTAINER,
                    GUNICORN_UWSGI_CONTAINER,
                ],
                forwarded_ports=[
                    PortForwarding(container_port=8080),
                ],
            ),
            marks=marks,
            id=f"Pod for {nginx_ctr.baseurl} with user {user}",
        )

        NGINX_PROXY_PODS.append(pod)


USERS = [
    "root",
    "nginx",
    999,
    1000,
    1001,
    65534,
]


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
)
def check_nginx_response(host_port: int, message: str, path: str = "/"):
    """
    Check if nginx response matches message.
    """
    resp = requests.get(f"http://0.0.0.0:{host_port}{path}", timeout=60)
    resp.raise_for_status()
    assert message in resp.text


@pytest.mark.parametrize("ctr_image", NGINX_CONTAINERS)
@pytest.mark.parametrize("user", USERS)
def test_nginx_welcome_page(
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
    user: Union[str, int],
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

        check_nginx_response(host_port, "Welcome to nginx")


@pytest.mark.parametrize("ctr_image", NGINX_WITH_CUSTOM_CONF)
@pytest.mark.parametrize("user", USERS)
def test_nginx_custom_conf(
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
    user: Union[str, int],
):
    """
    Test that nginx takes the config we provided.

    Ensure that the user inside the container matches the UID/username
    defined in the container run command.

    Ensure that the nginx serves the message in the custom configuration.
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

        # The custom config uses port 8080 mapping
        host_port = launcher.container_data.forwarded_ports[1].host_port

        check_nginx_response(host_port, "This is a custom nginx config!")


@pytest.mark.parametrize(
    "pod_per_test", NGINX_PROXY_PODS, indirect=["pod_per_test"]
)
def test_nginx_proxy_in_pod(pod_per_test: PodData) -> None:
    """
    Test that nginx can proxy pass.

    Nginx is configured to have a small buffer size.
    Gunicorn is configured to return a sizeable response.

    This should stress test proxy buffering and temp paths.
    """
    user = pod_per_test.container_data[0].container.extra_launch_args[1]
    con = pod_per_test.container_data[0].connection

    # ensure that nginx is running with the user defined in the Pod extra_launch_args
    assert con.run_expect([0], "id -u -n").stdout.strip() == user

    host_port = pod_per_test.forwarded_ports[0].host_port

    check_nginx_response(host_port, "This is a proxy!", "/")

    check_nginx_response(host_port, "Hello from Gunicorn!", "/test-proxy")

    check_nginx_response(host_port, "Hello from Gunicorn!", "/test-uwsgi")
