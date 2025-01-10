"""This module contains the tests for the pcp container"""

import time

import requests

from bci_tester.data import PCP_CONTAINERS

CONTAINER_IMAGES = PCP_CONTAINERS


def test_systemd_status(auto_container):
    """Verify that :command:`systemctl` is present and works and that
    :file:`/etc/machine-id` exists.

    """
    assert auto_container.connection.exists("systemctl")
    assert auto_container.connection.file("/etc/machine-id").exists
    auto_container.connection.run_expect([0], "systemctl status")


def test_pcp_services_status(auto_container_per_test):
    """Check that the pcp services are healthy."""

    for service in ("pmcd", "pmlogger", "pmproxy", "pmie"):
        assert wait_for_service(auto_container_per_test, service), (
            f"Timed out waiting for {service} to start"
        )


def test_call_pmcd(auto_container_per_test):
    """Check that the ``pmcd`` service is started and that :command:`pmbrobe`
    functions.

    """
    assert wait_for_service(auto_container_per_test, "pmcd"), (
        "Timed out waiting for pmcd to start"
    )

    auto_container_per_test.connection.run_expect(
        [0], "pmprobe -v mem.physmem"
    )


def test_call_pmproxy(auto_container_per_test):
    """Check that the ``pmcd`` and ``pmproxy`` services have started and that
    the parameter ``mem.physmem`` can be queried via :command:`curl`.

    """
    port = auto_container_per_test.forwarded_ports[0].host_port
    for service in ("pmcd", "pmproxy"):
        assert wait_for_service(auto_container_per_test, service), (
            f"Timed out waiting for {service} to start"
        )

    resp = requests.get(
        f"http://localhost:{port}/metrics?names=mem.physmem", timeout=30
    )
    resp.raise_for_status()
    assert "mem_physmem" in resp.text


def wait_for_service(con, service):
    """Wait up to 60 seconds for service to be active."""

    for _ in range(60):
        if con.connection.run(f"systemctl is-active {service}").rc == 0:
            return True
        time.sleep(1)

    return False
