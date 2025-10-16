"""This module contains the tests for the valkey container."""

import socket
from typing import List

import pytest
from _pytest.mark import ParameterSet
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.container import container_and_marks_from_pytest_param
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import VALKEY_CONTAINERS

CONTAINER_IMAGES = VALKEY_CONTAINERS


def _generate_test_matrix() -> List[ParameterSet]:
    params = []

    for vk_cont_param in VALKEY_CONTAINERS:
        vk_cont = container_and_marks_from_pytest_param(vk_cont_param)[0]
        marks = vk_cont_param.marks
        ports = vk_cont.forwarded_ports
        params.append(pytest.param(vk_cont, marks=marks))

        params.append(
            pytest.param(
                DerivedContainer(
                    base=vk_cont,
                    forwarded_ports=ports,
                    extra_launch_args=(["--user", "valkey"]),
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
def test_valkey_ping(
    container_per_test: ContainerData,
):
    """Test that we can reach valkey port successfully."""
    host_port = container_per_test.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_valkey_response():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("0.0.0.0", host_port))
        sock.sendall(b"PING\n")
        assert sock.recv(5) == b"+PONG"

    check_valkey_response()
