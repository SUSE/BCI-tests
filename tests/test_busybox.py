"""Test module performing simple smoke tests for the busybox container image."""

from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.selinux import selinux_status

CONTAINER_IMAGES = [BUSYBOX_CONTAINER]


def test_busybox_provides_sh(auto_container):
    """Check that /bin/sh is coming from busybox and not from bash."""
    assert (
        "BusyBox"
        in auto_container.connection.run_expect([0], "sh --help").stderr
    )


@pytest.mark.parametrize(
    "container",
    [BUSYBOX_CONTAINER],
    indirect=["container"],
)
def test_busybox_image_size(container, container_runtime):
    """Check that the size of the busybox container is below the accepted limits."""

    size: Dict[str, int] = {
        "x86_64": 16 if OS_VERSION == "tumbleweed" else 13,
        "aarch64": 16 if OS_VERSION == "tumbleweed" else 13,
        "s390x": 16 if OS_VERSION == "tumbleweed" else 13,
        "ppc64le": 16 if OS_VERSION == "tumbleweed" else 13,
    }

    if OS_VERSION.startswith("16"):
        size = {
            "x86_64": 14,
            "aarch64": 14,
            "s390x": 14,
            "ppc64le": 14,
        }

    container_size = container_runtime.get_image_size(
        container.image_url_or_id
    ) // (1024 * 1024)
    min_container_size = size[LOCALHOST.system_info.arch] - 5
    max_container_size = size[LOCALHOST.system_info.arch]
    assert container_size <= max_container_size, (
        f"Base container size is {container_size} MiB for {LOCALHOST.system_info.arch} "
        f"(expected {min_container_size}..{max_container_size} MiB)"
    )


def test_busybox_links(auto_container):
    """Ensure all binaries in :file:`/bin` are links to :file:`/usr/bin/busybox`."""
    auto_container.connection.check_output(
        'for i in /bin/*; do stat -c "%N" "$i" | grep -qE "(busybox|zmore|zless|zgrep|ldd|gencat|getent|locale|iconv|localedef|ld-linux|getconf)"; done',
    )


def test_busybox_binary_works(auto_container):
    """Ensure the busybox binary works"""
    auto_container.connection.check_output("busybox")


def test_true(auto_container):
    """Test if the busybox `true` and `false` commands are working"""
    auto_container.connection.run_expect([0], "true")
    auto_container.connection.run_expect([1], "false")


def test_echo_cat_grep_pipes(auto_container):
    """Test if a string gets passed correctly between `echo`, `cat` and `grep`"""
    auto_container.connection.run_expect(
        [0], "echo 'test' | cat | grep 'test'"
    )


def test_ps(auto_container):
    """Check if the `ps` command yields some output"""
    assert "root" in auto_container.connection.check_output("ps")


def test_base32_64(auto_container):
    """Ensure the base32 and base64 commands are returning the correct result for a given "test" string"""
    assert "ORSXG5AK" in auto_container.connection.check_output(
        "echo test | base32"
    )
    assert "dGVzdAo=" in auto_container.connection.check_output(
        "echo test | base64"
    )


@pytest.mark.parametrize(
    "container_per_test", [BUSYBOX_CONTAINER], indirect=True
)
def test_busybox_adduser(container_per_test):
    """Ensure the adduser command works and a new user can be created"""
    res = container_per_test.connection.run_expect([0, 1], "adduser -D foo")
    if res.rc == 1 and selinux_status() == "enforcing":
        pytest.xfail("https://bugzilla.suse.com/show_bug.cgi?id=1248283")
    assert res.rc == 0, f"adduser command failed with {res.stderr}"

    getent_passwd = container_per_test.connection.run_expect(
        [0], "getent passwd foo"
    )
    assert "foo" in getent_passwd.stdout
    container_per_test.connection.check_output("su - foo")
