"""This module contains the tests for the pcp container
"""
import time

from pytest_container.runtime import LOCALHOST

from bci_tester.data import PCP_CONTAINER

CONTAINER_IMAGES = [PCP_CONTAINER]


def test_systemd_status(auto_container_per_test):
    auto_container_per_test.connection.run_expect([0], "systemctl status")


def test_pcp_services_status(auto_container_per_test):
    """Check that the pcp services are healthy."""

    for service in ("pmcd", "pmlogger", "pmproxy", "pmie"):
        assert wait_for_service(
            auto_container_per_test, service
        ), f"Timed out waiting for {service} to start"


def test_call_pmcd(auto_container_per_test):
    assert wait_for_service(
        auto_container_per_test, "pmcd"
    ), "Timed out waiting for pmcd to start"

    auto_container_per_test.connection.run_expect(
        [0], "pmprobe -v mem.physmem"
    )


def test_call_pmproxy(auto_container_per_test):
    for service in ("pmcd", "pmproxy"):
        assert wait_for_service(
            auto_container_per_test, service
        ), f"Timed out waiting for {service} to start"

    if LOCALHOST.exists("curl"):
        assert LOCALHOST.run_expect(
            [0],
            "curl -s http://localhost:44322/metrics?names=mem.physmem",
        )


def wait_for_service(con, service):
    """Wait up to 60 seconds for service to be active."""

    for _ in range(60):
        rc = con.connection.run(f"systemctl is-active {service}").rc
        if rc == 0:
            return True
        time.sleep(1)

    return False
