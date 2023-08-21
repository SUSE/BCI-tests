"""This module contains the tests for the nginx container, the image with nginx pre-installed.
"""
import requests
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import NGINX_CONTAINER

CONTAINER_IMAGES = (NGINX_CONTAINER,)


def test_nginx_welcome_page(auto_container):
    """test that the default welcome page is served by the container."""
    host_port = auto_container.forwarded_ports[0].host_port

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
