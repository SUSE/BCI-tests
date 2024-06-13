"""Tests for the Prometheus containers."""

import pytest
import requests
from pytest_container.container import ContainerData

from bci_tester.data import PROMETHEUS_CONTAINERS


@pytest.mark.parametrize("container", PROMETHEUS_CONTAINERS, indirect=True)
def test_prometheus_ready(container: ContainerData) -> None:
    """Simple smoke test verifying that Prometheus is ready."""

    port = container.forwarded_ports[0].host_port
    resp = requests.get(f"http://localhost:{port}/-/ready", timeout=2)
    baseurl = container.container.baseurl
    assert baseurl
    assert resp.status_code == 200
    assert resp.text == "Prometheus Server is Ready.\n"


@pytest.mark.parametrize("container", PROMETHEUS_CONTAINERS, indirect=True)
def test_prometheus_healthy(container: ContainerData) -> None:
    """Simple smoke test verifying that Prometheus is healthy."""

    port = container.forwarded_ports[0].host_port
    resp = requests.get(f"http://localhost:{port}/-/healthy", timeout=2)
    assert resp.status_code == 200
    assert resp.text == "Prometheus Server is Healthy.\n"
