"""This module contains the tests for the pcp container
"""
import time

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import PCP_CONTAINER
from bci_tester.runtime_choice import DOCKER_SELECTED


@pytest.mark.parametrize("container", [PCP_CONTAINER], indirect=True)
@pytest.mark.skipif(DOCKER_SELECTED, reason="only podman is supported")
def test_systemd_present(container):
    """Check that the pcp daemons are running."""

    # pcp needs a little time to initialize
    time.sleep(5)

    assert container.connection.run_expect([0], "systemctl status")
    assert container.connection.run_expect([0], "systemctl status pmcd")
    assert container.connection.run_expect([0], "systemctl status pmlogger")
    assert container.connection.run_expect([0], "systemctl status pmproxy")
    assert container.connection.run_expect([0], "systemctl status pmie")

    # test call to pmcd
    assert container.connection.run_expect([0], "pmprobe -v mem.physmem")

    # test call to pmproxy
    if LOCALHOST.exists("curl"):
        assert LOCALHOST.run_expect(
            [0],
            "curl -s http://localhost:44322/metrics?names=mem.physmem",
        )
