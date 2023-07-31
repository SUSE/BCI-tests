"""This module contains the tests for the nginx container, the image with nginx pre-installed.
"""
from bci_tester.data import NGINX_CONTAINER


CONTAINER_IMAGES = (NGINX_CONTAINER,)


def test_nginx_welcome_page(auto_container, host):
    """test that the default welcome page is served by the container."""
    host_port = auto_container.forwarded_ports[0].host_port

    assert "Welcome to nginx" in host.check_output(
        f"curl -sf --retry 5 --retry-connrefused http://localhost:{host_port}/"
    )
