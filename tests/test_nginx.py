"""This module contains the tests for the nginx container, the image with nginx pre-installed."""

from typing import List

import pytest
import requests
from _pytest.mark import ParameterSet
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.container import container_and_marks_from_pytest_param
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import NGINX_CONTAINER

CONTAINER_IMAGES = (NGINX_CONTAINER,)


def _generate_test_matrix() -> List[ParameterSet]:
    params = []
    for ng_cont_param in CONTAINER_IMAGES:
        ng_cont = container_and_marks_from_pytest_param(ng_cont_param)[0]
        marks = ng_cont_param.marks
        ports = ng_cont.forwarded_ports
        params.append(pytest.param(ng_cont, marks=marks))

        params.append(
            pytest.param(
                DerivedContainer(
                    base=ng_cont,
                    forwarded_ports=ports,
                    extra_launch_args=(["--user", "nginx"]),
                ),
                marks=marks,
            )
        )

    return params


@pytest.mark.parametrize(
    "container_per_test",
    _generate_test_matrix(),
    indirect=["container_per_test"],
)
def test_nginx_welcome_page(
    container_per_test: ContainerData,
):
    """test that the default welcome page is served by the container."""
    host_port = container_per_test.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_nginx_response():
        resp = requests.get(f"http://localhost:{host_port}/", timeout=30)
        resp.raise_for_status()
        assert "Welcome to nginx" in resp.text

    check_nginx_response()
