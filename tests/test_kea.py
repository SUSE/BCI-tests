import re

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerLauncher
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import KEA_CONTAINERS

pytest.mark.parametrize("ctr_image", KEA_CONTAINERS)


def test_kea_dhcp4(
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
) -> None:
    kea_ctr = DerivedContainer(
        base=ctr_image,
        # below base image was used for testing as we haven't published kea image yet
        # base="registry.opensuse.org/devel/bci/tumbleweed/containerfile/opensuse/kea:latest",
        containerfile="COPY tests/files/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf",
        custom_entry_point="kea-dhcp4",
        extra_entrypoint_args=["-c", "/etc/kea/kea-dhcp4.conf"],
        extra_launch_args=["--network=host", "--privileged"],
    )

    dhcp_client_ctr = DerivedContainer(
        base="registry.opensuse.org/opensuse/tumbleweed:latest",
        containerfile="RUN zypper refresh && zypper -n install dhcp-client && zypper clean --all",
        custom_entry_point="/bin/sh",
        extra_launch_args=["--network=host", "--privileged"],
    )

    with ContainerLauncher.from_pytestconfig(
        kea_ctr, container_runtime, pytestconfig
    ) as kea_launcher, ContainerLauncher.from_pytestconfig(
        dhcp_client_ctr, container_runtime, pytestconfig
    ) as cli_launcher:
        kea_launcher.launch_container()
        cli_launcher.launch_container()

        cli_con = cli_launcher.container_data.connection
        client_log = cli_con.run_expect([0], "dhclient -v wlp0s20f3").stderr
        mac_pattern = r"LPF/\S+/([0-9a-fA-F:]+)"
        ip_pattern = r"bound to (\d+\.\d+\.\d+\.\d+)"
        mac_match = re.search(mac_pattern, client_log)
        ip_match = re.search(ip_pattern, client_log)

        client_mac = mac_match.group(1) if mac_match else None
        received_ip = ip_match.group(1) if ip_match else None
        assert client_mac is not None
        assert received_ip is not None

        kea_con = kea_launcher.container_data.connection
        log_lines = kea_con.check_output("cat /tmp/kea-dhcp4.log")
        pattern = r"DHCP4_LEASE_ALLOC .*?hwtype=1 ([\da-f:]+).*?lease ([\d.]+)"
        match = re.search(pattern, log_lines)
        if match:
            mac, ip = match.groups()
            assert mac == client_mac
            assert ip == received_ip
