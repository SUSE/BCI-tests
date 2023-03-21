"""This module contains the tests for the init container, the image with
systemd pre-installed.

"""
import datetime
import re
from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import INIT_CONTAINER
from bci_tester.runtime_choice import DOCKER_SELECTED

CONTAINER_IMAGES = [INIT_CONTAINER]


@pytest.mark.skipif(
    DOCKER_SELECTED
    and (int(LOCALHOST.package("systemd").version.split(".")[0]) >= 248),
    reason="Running systemd in docker is broken as of systemd 248, see https://github.com/moby/moby/issues/42275",
)
class TestSystemd:
    """
    systemd test module for the bci-init container.
    """

    def test_systemd_present(self, auto_container):
        """Check that :command:`systemctl` is in ``$PATH``, that :command:`systemctl
        status` works and that :file:`/etc/machine-id` exists.
        """
        assert auto_container.connection.exists("systemctl")
        assert auto_container.connection.file("/etc/machine-id").exists
        assert auto_container.connection.run_expect([0], "systemctl status")

    def test_systemd_boottime(self, auto_container):
        """Ensure the container startup time is below 5 seconds"""

        # Container startup time limit in seconds - aarch64 workers are slow sometimes.
        STARTUP_LIMIT = (
            11
            if auto_container.connection.system_info.arch == "aarch64"
            else 5.5
        )
        TARGET_LIMIT = STARTUP_LIMIT  # Limit for the systemd target to be reached in seconds

        def extract_time(stdout, prefix):
            """internal helper function to extract the time from systemd-analyze time
            extracts a timestamp with a given prefix and converts it to seconds
            Example:

            The received output of systemd-analzye time is the following:

            Startup finished in 505ms (userspace)
            graphical.target reached after 453ms in userspace

            For getting the startup time, use prefix = "Startup finished in " and the function will return 0.505s
            """
            i = stdout.find(prefix)
            if i < 0:
                raise ValueError(f"prefix {prefix} not found")
            t = (
                stdout[i + len(prefix) + 1 :].strip().split(" ")[0]
            )  # pick the the next word after the prefix, i.e. this should contain the time
            if t.endswith("ms"):
                return float(t[:-2]) / 1000.0
            if t.endswith("s"):
                return float(t[:-1])
            raise ValueError("time unit not recognized")

        time = auto_container.connection.run_expect(
            [0], "systemd-analyze time"
        )
        startup = extract_time(time.stdout, "Startup finished in ")
        assert startup <= STARTUP_LIMIT, "Startup threshold exceeded"
        target = extract_time(time.stdout, ".target reached after ")
        assert (
            target <= TARGET_LIMIT
        ), "Reaching systemd target threshold exceeded"

    def test_systemd_nofailed_units(self, auto_container):
        """
        Ensure there are no failed systemd units
        """
        output = auto_container.connection.run_expect(
            [0], "systemctl list-units --state=failed"
        )
        assert (
            "0 loaded units listed" in output.stdout
        ), "failed systemd units detected"

    def test_systemd_detect_virt(self, auto_container, container_runtime):
        """
        Ensure :command:`systemd-detect-virt` detects the container runtime
        """
        output = auto_container.connection.run_expect(
            [0], "systemd-detect-virt"
        ).stdout
        runtime = container_runtime.runner_binary
        assert (
            runtime in output
        ), f"systemd-detect-virt failed to detect {runtime}"

    def test_journald(self, auto_container):
        """
        Ensure :command:`journald` works correctly
        """

        # Check that we reached at least the multiuser target
        journal = auto_container.connection.run_expect(
            [0], "journalctl --boot"
        )
        assert (
            "Reached target Multi-User System" in journal.stdout
        ), "Multi-User target was not reached"

    def test_hostnamectl(self, auto_container, container_runtime):
        """
        Ensure :command:`hostnamectl` works correctly by asserting expected values
        """

        hostnamectl = auto_container.connection.run_expect([0], "hostnamectl")
        # Process the printed values to a string map
        values = TestSystemd._split_values(hostnamectl.stdout)
        assert values["Chassis"] == "container", "Chassis mismatch"
        assert (
            "SUSE Linux Enterprise Server" in values["Operating System"]
        ), "Missing SUSE tag in Operating system"
        assert (
            values["Virtualization"] == container_runtime.runner_binary
        ), "Virtualization tag mismatch"

    def test_timedatectl(self, auto_container):
        """
        Ensure :command:`timedatectl` works as expected and the container timezone is UTC
        """
        output = auto_container.connection.run_expect(
            [0], "timedatectl"
        ).stdout
        assert re.search(
            r"Time zone:.*(Etc/UTC|UTC)", output
        ), "Time zone not set to UTC"

        # Check that the reported timestamp for UTC and local time match the system time
        def check_timestamp(pattern, timestamp, delta):
            """Checks the timedatectl output for the given pattern against the given timestamp
            e.g. use the "Universal time" as pattern and datetime.utcnow() to check for the UTC time
            """
            grep = [line for line in output.split("\n") if pattern in line]
            assert (
                len(grep) == 1
            ), f"{pattern} not present in timedatectl output"
            tsp = (
                grep[0].strip()[len(pattern) + 2 :].strip()
            )  # Extract actual timestamp
            tsp = datetime.datetime.strptime(tsp, "%a %Y-%m-%d %H:%M:%S UTC")
            assert (
                abs(tsp - timestamp) < delta
            ), f"timedatectl diff exceeded for {pattern}"

        check_timestamp(
            "Universal time",
            datetime.datetime.utcnow(),
            datetime.timedelta(seconds=59),
        )
        # In the container the Local time is expected to be UTC
        check_timestamp(
            "Local time",
            datetime.datetime.utcnow(),
            datetime.timedelta(seconds=59),
        )

    def test_no_loginctl_sessions(self, auto_container):
        """
        Ensure :command:`loginctl` contains no logins
        """
        loginctl = auto_container.connection.run_expect([0], "loginctl")
        assert (
            "No sessions" in loginctl.stdout
        ), "Assert no sessions are present failed"

    @staticmethod
    def _split_values(output: str, sep: str = ":") -> Dict[str, str]:
        """Auxilliary function to process the given output into a key:value map, one entry by line"""
        ret = {}
        for line in output.split("\n"):
            tmp = line.strip().split(sep)
            if len(tmp) == 2:
                name, value = tmp[0].strip(), tmp[1].strip()
                ret[name] = value
        return ret
