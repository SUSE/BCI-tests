"""Test SUSE Private Registry

The set of containers heavily depend on each other and can not be tested individually.
We start them in a Podman Pod to let them interact and just call the health check api
provided by the core container and test for the overall status being "healthy".

"""

from pathlib import Path

import pytest
import requests
import tenacity
from pytest_container import BindMount
from pytest_container import Container
from pytest_container.container import ContainerVolume
from pytest_container.container import PortForwarding
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import BASEURL
from bci_tester.data import OS_VERSION
from bci_tester.data import TARGET

SPR_CONFIG_DIR = Path(__file__).parent.parent / "tests" / "files" / "spr"

SPR_CONFIG = {
    "db": {
        "name": "postgresql",
        "volumes": [ContainerVolume("/var/lib/postgresql/data")],
    },
    "valkey": {
        "name": "redis",
        "volumes": [ContainerVolume("/var/lib/valkey")],
    },
    "registry": {
        "volumes": [
            ContainerVolume("/storage"),
            BindMount(
                "/etc/registry", host_path=str(SPR_CONFIG_DIR / "registry")
            ),
            BindMount(
                "/etc/registry/root.crt",
                host_path=str(
                    SPR_CONFIG_DIR / "secret" / "registry" / "root.crt"
                ),
            ),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
    "registryctl": {
        "volumes": [
            ContainerVolume("/storage"),
            BindMount(
                "/etc/registry", host_path=str(SPR_CONFIG_DIR / "registry")
            ),
            BindMount(
                "/etc/registryctl/config.yml",
                host_path=str(SPR_CONFIG_DIR / "registryctl" / "config.yml"),
            ),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
    "core": {
        "volumes": [
            ContainerVolume("/data"),
            ContainerVolume("/etc/core/ca"),
            BindMount(
                "/etc/core/app.conf",
                host_path=str(SPR_CONFIG_DIR / "core" / "app.conf"),
            ),
            BindMount(
                "/etc/core/certificates",
                host_path=str(SPR_CONFIG_DIR / "core" / "certificates"),
            ),
            BindMount(
                "/etc/core/private_key.pem",
                host_path=str(
                    SPR_CONFIG_DIR / "secret" / "core" / "private_key.pem"
                ),
            ),
            BindMount(
                "/etc/core/key",
                host_path=str(
                    SPR_CONFIG_DIR / "secret" / "keys" / "secretkey"
                ),
            ),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
    "portal": {
        "volumes": [
            BindMount(
                "/etc/nginx/nginx.conf",
                host_path=str(SPR_CONFIG_DIR / "portal" / "nginx.conf"),
            ),
        ]
    },
    "jobservice": {
        "volumes": [
            ContainerVolume("/var/log/jobs"),
            BindMount(
                "/etc/jobservice/config.yml",
                host_path=str(SPR_CONFIG_DIR / "jobservice" / "config.yml"),
            ),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
    "exporter": {
        "volumes": [
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
    "trivy-adapter": {
        "volumes": [
            ContainerVolume("/home/scanner/.cache/trivy"),
            ContainerVolume("/home/scanner/.cache/reports"),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
    "nginx": {
        "name": "proxy",
        "volumes": [
            BindMount("/etc/nginx", host_path=str(SPR_CONFIG_DIR / "nginx")),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(
                    SPR_CONFIG_DIR / "shared" / "trust-certificates"
                ),
            ),
        ],
    },
}


def _get_repo() -> str:
    return "" if TARGET in ("ibs-released",) else "containerfile/"


SPR_CONTAINERS_FOR_POD = []

for img, conf in SPR_CONFIG.items():
    # Disable pylint check because I don't classify these as constants. Sorry
    build_tag = f"private-registry/harbor-{img}:latest"  # pylint: disable=C0103
    baseurl = f"{BASEURL}/{_get_repo()}{build_tag}"  # pylint: disable=C0103

    launch_args = [f"--name={conf.get('name', img)}"]

    env_file = SPR_CONFIG_DIR / img / "env"
    if env_file.is_file():
        launch_args.append(f"--env-file={env_file}")

    SPR_CONTAINERS_FOR_POD.append(
        Container(
            url=baseurl,
            volume_mounts=conf["volumes"],
            extra_launch_args=launch_args,
        )
    )

HARBOR_POD = Pod(
    containers=SPR_CONTAINERS_FOR_POD,
    forwarded_ports=[
        PortForwarding(container_port=8080),
        PortForwarding(container_port=9090),
    ],
)


@pytest.mark.skipif(
    OS_VERSION not in ("15.6-spr",),
    reason="Harbor is only tested for SUSE Private Registry",
)
@pytest.mark.parametrize(
    "pod_per_test", [HARBOR_POD], indirect=["pod_per_test"]
)
def test_harbor_in_pod(pod_per_test: PodData) -> None:
    """
    Start all of harbor's components in a pod and call the health-api
    check if it returns an overall health status of "healthy"
    """

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
        stop=tenacity.stop_after_attempt(8), wait=tenacity.wait_exponential()
    )
    def check_health(port: int):
        resp = get_health(port)
        data = resp.json()
        if data["status"] != "healthy":
            raise RuntimeError("FAIL: Status is not healthy")
        return True

    assert check_health(pod_per_test.forwarded_ports[0].host_port), (
        "Status is not healthy"
    )
