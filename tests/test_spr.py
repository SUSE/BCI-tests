"""Test SUSE Private Registry

The set of containers heavily depend on each other and can not be tested individually.
We start them in a Podman Pod to let them interact and just call the health check api
provided by the core container and test for the overall status being "healthy".

"""

import pytest
import requests
import tenacity
from pytest_container.container import EntrypointSelection
from pytest_container.container import PortForwarding
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import SPR_CONTAINERS

SPR_CONTAINERS_FOR_POD = []
for param in SPR_CONTAINERS:
    ctr = container_and_marks_from_pytest_param(param)[0]
    ctr.entry_point = EntrypointSelection.AUTO
    SPR_CONTAINERS_FOR_POD.append(ctr)

HARBOR_POD = Pod(
    containers=SPR_CONTAINERS_FOR_POD,
    forwarded_ports=[
        PortForwarding(container_port=8080),
        PortForwarding(container_port=9090),
    ],
)


@pytest.mark.parametrize(
    "pod_per_test", [HARBOR_POD], indirect=["pod_per_test"]
)
def test_harbor_in_pod(pod_per_test: PodData) -> None:
    def get_health(port: int) -> requests.Response:
        headers = {"accept": "application/json"}
        r = requests.get(
            f"http://0.0.0.0:{port}/api/v2.0/health",
            headers=headers,
            timeout=3,
            allow_redirects=True,
        )
        r.raise_for_status()
        return r

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
    )
    def check_health(port: int):
        resp = get_health(port)
        data = resp.json()
        if data["status"] != "healthy":
            raise RuntimeError("FAIL: Status is not healthy")
        return True

    # breakpoint()
    assert check_health(pod_per_test.forwarded_ports[0].host_port), (
        "Status is not healthy"
    )
