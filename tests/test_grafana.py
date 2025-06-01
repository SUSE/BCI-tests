"""Tests for the Grafana containers."""

import pytest
import requests
import tenacity
from pytest_container.container import ContainerData

from bci_tester.data import GRAFANA_CONTAINERS


@pytest.mark.parametrize("container", GRAFANA_CONTAINERS, indirect=True)
def test_prometheus_healthy(container: ContainerData) -> None:
    """Simple smoke test verifying that Grafana is healthy."""

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
    )
    def _fetch_grafana_health() -> requests.Response:
        port = container.forwarded_ports[0].host_port
        resp = requests.get(f"http://localhost:{port}/api/health", timeout=2)
        resp.raise_for_status()
        return resp

    resp = _fetch_grafana_health()
    resp.raise_for_status()
    data = resp.json()
    if "+" in data["version"]:
        data["version"] = data["version"].partition("+")[0]
    grafana_version = container.inspect.config.labels[
        "org.opencontainers.image.version"
    ]
    assert data == {
        "commit": "NA",
        "database": "ok",
        "version": grafana_version,
    }
