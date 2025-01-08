import os

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerLauncher
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import KUBECTL_CONTAINERS


@pytest.mark.parametrize("ctr_image", KUBECTL_CONTAINERS)
def test_kubectl(
    host,
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
) -> None:
    engine = container_runtime.runner_binary
    cluster_name = os.getenv("K3S_CLUSTER_NAME")
    control_plane = "k3d-" + cluster_name + "-server-0"
    host.run_expect([0], f"k3d kubeconfig get {cluster_name} > kubeconfig")
    format_template = (
        "'{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'"
    )
    kind_ip = host.check_output(
        f"{engine} inspect -f {format_template} {control_plane}"
    )
    host.run_expect(
        [0],
        rf'sed -i "s/server: https:\/\/.*:[0-9]*/server: https:\/\/{kind_ip}:6443/g" kubeconfig',
    )

    kubectl_ctr = DerivedContainer(
        base=ctr_image,
        # below base image was used for testing as we haven't published kubectl image yet
        # base="registry.opensuse.org/home/defolos/bci/staging/tumbleweed/tumbleweed-2060/containerfile/opensuse/kubectl:latest",
        containerfile="COPY kubeconfig /root/.kube/config",
        custom_entry_point="/bin/bash",
        extra_launch_args=["--network=" + "k3d-" + cluster_name],
    )

    with ContainerLauncher.from_pytestconfig(
        kubectl_ctr, container_runtime, pytestconfig
    ) as kubectl_launcher:
        kubectl_launcher.launch_container()
        kubectl_con = kubectl_launcher.container_data.connection
        nodes = (
            kubectl_con.check_output("kubectl get nodes").strip().splitlines()
        )
        assert len(nodes) == 2
        assert control_plane == nodes[1].split()[0]
