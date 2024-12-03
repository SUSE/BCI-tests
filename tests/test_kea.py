import pytest
from pytest_container import DerivedContainer
from bci_tester.data import KEA_CONTAINERS

pytest.mark.parametrize("ctr_image", KEA_CONTAINERS)
def test_kea_dhcp4(
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
) -> None:
    
    ## Notes (will be removed)
    # entry point kea-dhcp4
    # -c /etc/kea/kea-dhcp4.conf
    # extra run args
    # mounts: List[Union[BindMount, ContainerVolume]] = [
    #     BindMount(host_path=tmp_path, container_path="/etc")
    # ]
    # DOCKERFILE = """WORKDIR /src/
    # COPY tests/files/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf
    # """

    kea_ctr = DerivedContainer(
        base=ctr_image,
        containerfile='COPY tests/files/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf',
        custom_entry_point="kea-dhcp4",
        extra_run_args=["--network=host", "--previleged", "-c", "/etc/kea/kea-dhcp4.conf"],
    )

    dhcp_client_ctr = DerivedContainer(
        base="registry.opensuse.org/opensuse/tumbleweed:latest",
        containerfile='RUN zypper install dhcp-client',
        custom_entry_point="/bin/sh"
    )

    
    with ContainerLauncher.from_pytestconfig(
        kea_ctr, container_runtime, pytestconfig
    ) as launcher:
        launcher.launch_container()
        con = launcher.container_data.connection

        with ContainerLauncher.from_pytestconfig(
            dhcp_client_ctr, container_runtime, pytestconfig
        ) as launcher:
            launcher.launch_container()
            con = launcher.container_data.connection
            # yet to check output and assert with regex
            ip_addr = con.check_output("dhclient -v")
            assert ip_addr != ""