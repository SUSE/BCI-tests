from pathlib import Path

import pytest
import requests
import tenacity
from dotenv import dotenv_values
from pytest_container.container import BindMount
from pytest_container.container import Container
from pytest_container.container import ContainerVolume
from pytest_container.container import PortForwarding
from pytest_container.pod import Pod
from pytest_container.pod import PodData

_conf_dir = Path(__file__).parent / "files" / "harbor"

_envs = {}

for cont in (
    "core",
    "db",
    "exporter",
    "jobservice",
    "registryctl",
    "trivy-adapter",
):
    _envs[cont] = dotenv_values(str(_conf_dir / cont / "env"))

_volumes = {
    "registry": [
        ContainerVolume("/storage"),
        BindMount("/etc/registry", host_path=str(_conf_dir / "registry")),
        BindMount(
            "/etc/registry/root.crt",
            host_path=str(_conf_dir / "secret" / "registry" / "root.crt"),
        ),
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
    "registryctl": [
        ContainerVolume("/storage"),
        BindMount("/etc/registry", host_path=str(_conf_dir / "registry")),
        BindMount(
            "/etc/registryctl/config.yml",
            host_path=str(_conf_dir / "registryctl" / "config.yml"),
        ),
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
    "core": [
        ContainerVolume("/data"),
        ContainerVolume("/etc/core/ca"),
        BindMount(
            "/etc/core/app.conf",
            host_path=str(_conf_dir / "core" / "app.conf"),
        ),
        BindMount(
            "/etc/core/certificates",
            host_path=str(_conf_dir / "core" / "certificates"),
        ),
        BindMount(
            "/etc/core/private_key.pem",
            host_path=str(_conf_dir / "secret" / "core" / "private_key.pem"),
        ),
        BindMount(
            "/etc/core/key",
            host_path=str(_conf_dir / "secret" / "keys" / "secretkey"),
        ),
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
    "db": [ContainerVolume("/var/lib/postgresql/data")],
    "portal": [
        BindMount(
            "/etc/nginx/nginx.conf",
            host_path=str(_conf_dir / "portal" / "nginx.conf"),
        ),
    ],
    "jobservice": [
        ContainerVolume("/var/log/jobs"),
        BindMount(
            "/etc/jobservice/config.yml",
            host_path=str(_conf_dir / "jobservice" / "config.yml"),
        ),
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
    "valkey": [ContainerVolume("/var/lib/valkey")],
    "nginx": [
        BindMount("/etc/nginx", host_path=str(_conf_dir / "nginx")),
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
    "trivy-adapter": [
        ContainerVolume("/home/scanner/.cache/trivy"),
        ContainerVolume("/home/scanner/.cache/reports"),
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
    "exporter": [
        BindMount(
            "/harbor_cust_cert",
            host_path=str(_conf_dir / "shared" / "trust-certificates"),
        ),
    ],
}

_forwarded_ports = [
    PortForwarding(container_port=8080),
    PortForwarding(container_port=9090),
]

OBS_PROJECT = (
    "registry.suse.de/devel/scc/privateregistry/containerfile/private-registry"
)
# OBS_PROJECT = "registry.suse.de/devel/scc/staging/privateregistry/ci/mr-15/containerfile/private-registry"

HARBOR_CONTAINERS = [
    Container(
        url=f"{OBS_PROJECT}/harbor-{img}:latest",
        extra_environment_variables=_envs.get(img, {}),
        volume_mounts=_volumes[img],
        extra_launch_args=[f"--name={name}"],
    )
    for img, name in (
        ("db", "postgresql"),
        ("valkey", "redis"),
        ("registry", "registry"),
        ("registryctl", "registryctl"),
        ("core", "core"),
        ("portal", "portal"),
        ("jobservice", "jobservice"),
        ("exporter", "exporter"),
        ("trivy-adapter", "trivy-adapter"),
        ("nginx", "proxy"),
    )
]

HARBOR_POD = Pod(
    containers=HARBOR_CONTAINERS, forwarded_ports=_forwarded_ports
)


@pytest.mark.parametrize(
    "pod_per_test", [HARBOR_POD], indirect=["pod_per_test"]
)
def test_harbor_in_pod(pod_per_test: PodData) -> None:
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
    )
    def get_health(port: int) -> requests.Response:
        headers = {"accept": "application/json"}
        return requests.get(
            f"http://0.0.0.0:{port}/api/v2.0/health",
            headers=headers,
            timeout=3,
            allow_redirects=True,
        )

    # breakpoint()
    resp = get_health(pod_per_test.forwarded_ports[0].host_port)
    assert resp.status_code == requests.codes.ok, "Could not get health status"

    print(resp.text)

    data = resp.json()
    assert data["status"] == "healthy", "Status is not healthy"
