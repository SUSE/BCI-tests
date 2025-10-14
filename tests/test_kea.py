"""Tests for validating the KEA DHCP Server image."""

import json
import os
import re

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerLauncher
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import KEA_CONTAINERS
from bci_tester.runtime_choice import DOCKER_SELECTED


@pytest.mark.parametrize("ctr_image", KEA_CONTAINERS)
def test_kea_dhcp4(
    container_runtime: OciRuntimeBase,
    host,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
) -> None:
    network_name = "macvlan-network"
    kea_config_file = "tests/files/kea-dhcp4.conf"
    dhclient_config_file_path = "/etc/dhclient.conf"
    request_ip = "172.25.1.107"
    with open(kea_config_file, "r") as f:
        config = json.load(f)
    subnet = config["Dhcp4"]["subnet4"][0]["subnet"]
    gateway = config["Dhcp4"]["subnet4"][0]["option-data"][0]["data"]
    network_create_cmd = f"{container_runtime.runner_binary} network create "
    dummy_nic = "dummy0"
    use_macvlan_dummy = os.getenv("USE_MACVLAN_DUMMY") == "1"
    if DOCKER_SELECTED or os.getuid() == 0:
        network_create_cmd += "--driver macvlan "
        if use_macvlan_dummy:
            host.check_output(f"ip link delete {dummy_nic} || true")
            host.check_output(
                f"ip link add {dummy_nic} type dummy && ip link set {dummy_nic} up"
            )
            network_create_cmd += f"-o parent={dummy_nic} "
    else:
        network_create_cmd += "--internal "
    network_create_cmd += (
        f" --subnet={subnet} --gateway={gateway} {network_name}"
    )
    host.check_output(network_create_cmd)

    kea_ctr = DerivedContainer(
        base=ctr_image,
        containerfile="COPY tests/files/kea-dhcp4.conf /etc/kea/kea-dhcp4.conf",
        custom_entry_point="kea-dhcp4",
        extra_entrypoint_args=["-c", "/etc/kea/kea-dhcp4.conf"],
        extra_launch_args=[f"--network={network_name}", "--privileged"],
    )

    dhcp_client_ctr = DerivedContainer(
        base=container_and_marks_from_pytest_param(BASE_CONTAINER)[0],
        containerfile="RUN zypper refresh && zypper -n install dhcp-client jq && zypper clean --all",
        custom_entry_point="/bin/sh",
        extra_launch_args=[f"--network={network_name}", "--privileged"],
    )

    try:
        with ContainerLauncher.from_pytestconfig(
            kea_ctr, container_runtime, pytestconfig
        ) as kea_launcher, ContainerLauncher.from_pytestconfig(
            dhcp_client_ctr, container_runtime, pytestconfig
        ) as cli_launcher:
            kea_launcher.launch_container()
            cli_launcher.launch_container()

            cli_con = cli_launcher.container_data.connection
            # get the default interface name
            default_interface = cli_con.check_output(
                "ip -j link show up | jq -r '.[] | select(.link_type == \"ether\") | .ifname'"
            ).strip()

            # configure dhcp client to request a specific ip i.e in the range specified in kea-dhcp
            # configuration file to make sure that ip is received from kea server
            cli_con.check_output(
                "echo -e 'interface \""
                + default_interface
                + '" {\n send dhcp-requested-address '
                + request_ip
                + ";\n }' >> "
                + dhclient_config_file_path,
            )

            # request a specific ip by passing the configuration file
            client_log = cli_con.run_expect(
                [0],
                "timeout 1m "
                + "dhclient -cf "
                + dhclient_config_file_path
                + " -v "
                + default_interface,
            ).stderr

            # Extracts a MAC address (e.g., 00:1A:2B:3C:4D:5E) from a string like 'LPF/eth0/00:1A:2B:3C:4D:5E' using named group 'mac'.
            mac_pattern = r"LPF/\S+/(?P<mac>[0-9a-fA-F:]+)"
            mac_match = re.search(mac_pattern, client_log)
            client_mac = mac_match.group("mac") if mac_match else None
            assert client_mac is not None

            # Matches "bound to 172.25.1.100" and captures an IPv4 address (e.g., 172.25.1.100) in the 'ip' named group.
            ip_pattern = r"bound to (?P<ip>\d+\.\d+\.\d+\.\d+)"
            ip_match = re.search(ip_pattern, client_log)
            received_ip = ip_match.group("ip") if ip_match else None
            assert received_ip == request_ip

            kea_con = kea_launcher.container_data.connection
            log_lines = kea_con.file(
                "/var/log/kea/kea-dhcp4.log"
            ).content_string
            # Matches DHCP4 lease allocation log entries (e.g., "DHCP4_LEASE_ALLOC [hwtype=1 02:42:ac:19:00:03], cid=[no info], tid=0x7379cf19: lease 172.25.1.100") and captures MAC and IP.
            pattern = r"DHCP4_LEASE_ALLOC .*?hwtype=1 (?P<mac>[\da-f:]+).*?lease (?P<ip>[\d.]+)"
            match = re.search(pattern, log_lines)
            if not match:
                pytest.fail("IP is not allocated by the kea dhcp server")

            mac = match.group("mac")
            ip = match.group("ip")
            assert mac == client_mac
            assert ip == request_ip
    finally:
        if use_macvlan_dummy:
            host.check_output(f"ip link delete {dummy_nic}")
        host.check_output(
            f"{container_runtime.runner_binary} network rm {network_name}"
        )
