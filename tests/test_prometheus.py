"""Tests for the Prometheus containers."""

import pytest
import requests
from pytest_container.container import ContainerData

from bci_tester.data import ALERTMANAGER_CONTAINERS
from bci_tester.data import BLACKBOX_CONTAINERS
from bci_tester.data import PROMETHEUS_CONTAINERS

PROMETHEUS_STACK_CONTAINERS = PROMETHEUS_CONTAINERS + ALERTMANAGER_CONTAINERS
PROMETHEUS_AND_BLACKBOX_CONTAINERS = (
    PROMETHEUS_CONTAINERS + ALERTMANAGER_CONTAINERS + BLACKBOX_CONTAINERS
)


@pytest.mark.parametrize(
    "container", PROMETHEUS_STACK_CONTAINERS, indirect=True
)
def test_prometheus_ready(container: ContainerData) -> None:
    """Simple smoke test verifying that Prometheus is ready."""

    port = container.forwarded_ports[0].host_port
    resp = requests.get(f"http://localhost:{port}/-/ready", timeout=2)
    assert resp.status_code == 200
    assert resp.text in ["Prometheus Server is Ready.\n", "OK"]


@pytest.mark.parametrize(
    "container", PROMETHEUS_AND_BLACKBOX_CONTAINERS, indirect=True
)
def test_prometheus_healthy(container: ContainerData) -> None:
    """Simple smoke test verifying that Prometheus is healthy."""

    port = container.forwarded_ports[0].host_port
    resp = requests.get(f"http://localhost:{port}/-/healthy", timeout=2)
    assert resp.status_code == 200
    assert resp.text in ["Prometheus Server is Healthy.\n", "OK", "Healthy"]
