"""This module contains the tests for the init container, the image with
systemd pre-installed.

"""

import datetime
import json
import re

import pytest
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import INIT_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.runtime_choice import DOCKER_SELECTED

CONTAINER_IMAGES = [INIT_CONTAINER]


pytestmark = pytest.mark.skipif(
    DOCKER_SELECTED
    and (int(LOCALHOST.package("systemd").version.split(".")[0]) >= 248),
    reason="Running systemd in docker is broken as of systemd 248, see https://github.com/moby/moby/issues/42275",
)


def test_systemd_present(auto_container: ContainerData):
    """Check that :command:`systemctl` is in ``$PATH``, that :command:`systemctl
    status` works and that :file:`/etc/machine-id` exists.
    """
    assert auto_container.connection.exists("systemctl")
    assert auto_container.connection.file("/etc/machine-id").exists
    assert auto_container.connection.check_output("systemctl status")


def test_systemd_no_udev_present(auto_container: ContainerData):
    """https://jira.suse.com/browse/SLE-21856 - check that systemd is not pulling in
    udev.
    """
    assert not auto_container.connection.package("udev").is_installed


def test_systemd_boottime(auto_container: ContainerData):
    """Ensure the container startup time is below 5 seconds"""

    # https://github.com/SUSE/BCI-tests/issues/647
    if auto_container.connection.system_info.arch == "ppc64le":
        pytest.skip(
            "boottime test temporarily disabled on emulated ppc64le workers."
        )

    # Container startup time limit in seconds - aarch64 workers are slow sometimes.
    startup_limit = (
        11 if auto_container.connection.system_info.arch == "aarch64" else 5.5
    )
    target_limit = (
        startup_limit  # Limit for the systemd target to be reached in seconds
    )

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

    time = auto_container.connection.check_output("systemd-analyze time")
    startup = extract_time(time, "Startup finished in ")
    assert startup <= startup_limit, "Startup threshold exceeded"
    target = extract_time(time, ".target reached after ")
    assert target <= target_limit, "Reaching systemd target threshold exceeded"


def test_systemd_nofailed_units(auto_container: ContainerData):
    """
    Ensure there are no failed systemd units
    """
    output = auto_container.connection.check_output(
        "systemctl list-units --state=failed"
    )
    assert "0 loaded units listed" in output, "failed systemd units detected"


def test_systemd_detect_virt(
    auto_container: ContainerData, container_runtime: OciRuntimeBase
):
    """
    Ensure :command:`systemd-detect-virt` detects the container runtime
    """
    output = auto_container.connection.check_output("systemd-detect-virt")
    runtime = container_runtime.runner_binary
    assert runtime in output, f"systemd-detect-virt failed to detect {runtime}"


def test_journald(auto_container: ContainerData):
    """
    Ensure :command:`journald` works correctly
    """

    # Check that we reached at least the multiuser target
    journal = auto_container.connection.check_output("journalctl --boot")
    assert "Reached target Multi-User System" in journal, (
        "Multi-User target was not reached"
    )


def test_hostnamectl(
    auto_container: ContainerData, container_runtime: OciRuntimeBase
):
    """
    Ensure :command:`hostnamectl` works correctly by asserting expected values
    """

    hostnamectl = json.loads(
        auto_container.connection.check_output("hostnamectl --json=short")
    )
    assert hostnamectl["Chassis"] == "container", "Chassis mismatch"

    expected_os = "SUSE Linux Enterprise Server"
    if OS_VERSION == "tumbleweed":
        expected_os = "openSUSE Tumbleweed"
    elif OS_VERSION in ("16.0",):
        expected_os = "SUSE Linux " + OS_VERSION

    assert expected_os in hostnamectl["OperatingSystemPrettyName"], (
        "Missing SUSE tag in Operating system"
    )

    assert (
        auto_container.connection.check_output(
            "systemd-detect-virt -c"
        ).strip()
        == container_runtime.runner_binary
    ), "Virtualization tag mismatch"


def test_timedatectl(auto_container: ContainerData):
    """
    Ensure :command:`timedatectl` works as expected and the container timezone is UTC
    """
    output = auto_container.connection.check_output("timedatectl")
    assert re.search(r"Time zone:.*(Etc/UTC|UTC)", output), (
        "Time zone not set to UTC"
    )

    # Check that the reported timestamp for UTC and local time match the system time
    def check_timestamp(pattern, timestamp, delta):
        """Checks the timedatectl output for the given pattern against the given timestamp
        e.g. use the "Universal time" as pattern and datetime.utcnow() to check for the UTC time
        """
        grep = [line for line in output.split("\n") if pattern in line]
        assert len(grep) == 1, f"{pattern} not present in timedatectl output"
        tsp = (
            grep[0].strip()[len(pattern) + 2 :].strip()
        )  # Extract actual timestamp
        tsp = datetime.datetime.strptime(tsp, "%a %Y-%m-%d %H:%M:%S UTC")
        assert abs(tsp - timestamp) < delta, (
            f"timedatectl diff exceeded for {pattern}"
        )

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


def test_no_loginctl_sessions(auto_container: ContainerData):
    """
    Ensure :command:`loginctl` contains no logins
    """
    loginctl = auto_container.connection.check_output("loginctl")
    assert "No sessions" in loginctl, "Assert no sessions are present failed"
