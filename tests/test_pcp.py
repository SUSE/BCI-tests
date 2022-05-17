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

    wait_for_pmcd(auto_container_per_test)

    auto_container_per_test.connection.run_expect([0], "systemctl status pmcd")
    auto_container_per_test.connection.run_expect(
        [0], "systemctl status pmlogger"
    )
    auto_container_per_test.connection.run_expect(
        [0], "systemctl status pmproxy"
    )
    auto_container_per_test.connection.run_expect([0], "systemctl status pmie")


def test_call_pmcd(auto_container_per_test):
    wait_for_pmcd(auto_container_per_test)
    auto_container_per_test.connection.run_expect(
        [0], "pmprobe -v mem.physmem"
    )


def test_call_pmproxy(auto_container_per_test):
    wait_for_pmcd(auto_container_per_test)
    if LOCALHOST.exists("curl"):
        assert LOCALHOST.run_expect(
            [0],
            "curl -s http://localhost:44322/metrics?names=mem.physmem",
        )


def wait_for_pmcd(con):
    """pmcd takes a little time to initialize things before it is ready"""

    for _ in range(30):
        rc = con.connection.run("systemctl is-active pmcd").rc
        if rc == 0:
            return
        time.sleep(1)

    assert False, "Timed out waiting for pmcd to start"
