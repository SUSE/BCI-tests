"""This module contains the tests for the valkey container."""

import socket

from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import VALKEY_CONTAINERS

CONTAINER_IMAGES = VALKEY_CONTAINERS


def test_valkey_ping(auto_container):
    """Test that we can reach valkey port successfully."""
    host_port = auto_container.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_valkey_response():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("0.0.0.0", host_port))
        sock.sendall(b"PING\n")
        assert sock.recv(4) == b"+PONG"

    check_valkey_response()
