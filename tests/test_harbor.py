from pathlib import Path

import pytest
import requests
import tenacity
from pytest_container.container import BindMount
from pytest_container.container import Container
from pytest_container.container import ContainerVolume
from pytest_container.container import PortForwarding
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import BASEURL
from bci_tester.data import OS_VERSION
from bci_tester.data import TARGET

_conf_dir = Path(__file__).parent / "files" / "harbor"

_forwarded_ports = [
    PortForwarding(container_port=8080),
    PortForwarding(container_port=9090),
]

OBS_PROJECT = BASEURL + "/containerfile/private-registry"

CONTAINER_DEF = {
    "db": {
        "name": "postgresql",
        "env": str(_conf_dir / "db" / "env"),
        "volumes": [ContainerVolume("/var/lib/postgresql/data")],
    },
    "valkey": {
        "name": "redis",
        "volumes": [ContainerVolume("/var/lib/valkey")],
    },
    "registry": {
        "volumes": [
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
    },
    "registryctl": {
        "env": str(_conf_dir / "registryctl" / "env"),
        "volumes": [
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
    },
    "core": {
        "env": str(_conf_dir / "core" / "env"),
        "volumes": [
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
                host_path=str(
                    _conf_dir / "secret" / "core" / "private_key.pem"
                ),
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
    },
    "portal": {
        "volumes": [
            BindMount(
                "/etc/nginx/nginx.conf",
                host_path=str(_conf_dir / "portal" / "nginx.conf"),
            ),
        ]
    },
    "jobservice": {
        "env": str(_conf_dir / "jobservice" / "env"),
        "volumes": [
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
    },
    "exporter": {
        "env": str(_conf_dir / "exporter" / "env"),
        "volumes": [
            BindMount(
                "/harbor_cust_cert",
                host_path=str(_conf_dir / "shared" / "trust-certificates"),
            ),
        ],
    },
    "trivy-adapter": {
        "env": str(_conf_dir / "trivy-adapter" / "env"),
        "volumes": [
            ContainerVolume("/home/scanner/.cache/trivy"),
            ContainerVolume("/home/scanner/.cache/reports"),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(_conf_dir / "shared" / "trust-certificates"),
            ),
        ],
    },
    "nginx": {
        "name": "proxy",
        "volumes": [
            BindMount("/etc/nginx", host_path=str(_conf_dir / "nginx")),
            BindMount(
                "/harbor_cust_cert",
                host_path=str(_conf_dir / "shared" / "trust-certificates"),
            ),
        ],
    },
}

HARBOR_CONTAINERS = []

for img, conf in CONTAINER_DEF.items():
    name = conf.get("name", img)
    launch_args = [f"--name={name}"]
    if conf.get("env"):
        launch_args.append(f"--env-file={conf['env']}")

    HARBOR_CONTAINERS.append(
        Container(
            url=f"{OBS_PROJECT}/harbor-{img}:latest",
            volume_mounts=conf["volumes"],
            extra_launch_args=launch_args,
        )
    )

HARBOR_POD = Pod(
    containers=HARBOR_CONTAINERS, forwarded_ports=_forwarded_ports
)


@pytest.mark.parametrize(
    "pod_per_test", [HARBOR_POD], indirect=["pod_per_test"]
)
@pytest.mark.skipif(
    OS_VERSION not in ("15.6-pr",),
    reason="Harbor tested for SUSE Private Registry only",
)
@pytest.mark.skipif(
    TARGET
    not in (
        "obs",
        "ibs-cr",
    ),
    reason="Harbor not avalable for this target",
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
