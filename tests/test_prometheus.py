"""Tests for the Prometheus containers."""

import pytest
import requests
from pytest_container.container import ContainerData

from bci_tester.data import PROMETHEUS_CONTAINERS
from bci_tester.data import ALERTMANAGER_CONTAINERS
from bci_tester.data import BLACKBOX_CONTAINERS


ready_containers = PROMETHEUS_CONTAINERS + ALERTMANAGER_CONTAINERS
healthy_containers = (
    PROMETHEUS_CONTAINERS + ALERTMANAGER_CONTAINERS + BLACKBOX_CONTAINERS
)


@pytest.mark.parametrize("container", ready_containers, indirect=True)
def test_prometheus_ready(container: ContainerData) -> None:
    """Simple smoke test verifying that Prometheus is ready."""

    port = container.forwarded_ports[0].host_port
    resp = requests.get(f"http://localhost:{port}/-/ready", timeout=2)
    baseurl = container.container.baseurl
    assert baseurl
    assert resp.status_code == 200
    assert resp.text in ["Prometheus Server is Ready.\n", "OK"]


@pytest.mark.parametrize("container", healthy_containers, indirect=True)
def test_prometheus_healthy(container: ContainerData) -> None:
    """Simple smoke test verifying that Prometheus is healthy."""

    port = container.forwarded_ports[0].host_port
    resp = requests.get(f"http://localhost:{port}/-/healthy", timeout=2)
    assert resp.status_code == 200
    assert resp.text in ["Prometheus Server is Healthy.\n", "OK", "Healthy"]
