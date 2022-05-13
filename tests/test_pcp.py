"""This module contains the tests for the pcp container
"""
import time

from pytest_container.runtime import LOCALHOST

from bci_tester.data import PCP_CONTAINER

CONTAINER_IMAGES = [PCP_CONTAINER]

def test_systemd_present(auto_container_per_test):
    """Check that the pcp daemons are running."""

    # pcp needs a little time to initialize
    time.sleep(5)

    auto_container_per_test.connection.run_expect([0], "systemctl status")
    auto_container_per_test.connection.run_expect([0], "systemctl status pmcd")
    auto_container_per_test.connection.run_expect([0], "systemctl status pmlogger")
    auto_container_per_test.connection.run_expect([0], "systemctl status pmproxy")
    auto_container_per_test.connection.run_expect([0], "systemctl status pmie")

    # test call to pmcd
    auto_container_per_test.connection.run_expect([0], "pmprobe -v mem.physmem")

    # test call to pmproxy
    if LOCALHOST.exists("curl"):
        assert LOCALHOST.run_expect(
            [0],
            "curl -s http://localhost:44322/metrics?names=mem.physmem",
        )
