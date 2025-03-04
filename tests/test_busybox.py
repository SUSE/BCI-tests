"""Test module performing simple smoke tests for the busybox container image."""

from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = [BUSYBOX_CONTAINER]


def test_busybox_provides_sh(auto_container):
    """Check that /bin/sh is coming from busybox and not from bash."""
    assert (
        "BusyBox"
        in auto_container.connection.run_expect([0], "sh --help").stderr
    )


#: size limits of the micro image per architecture in MiB
BUSYBOX_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 16 if OS_VERSION == "tumbleweed" else 13,
    "aarch64": 16 if OS_VERSION == "tumbleweed" else 13,
    "s390x": 16 if OS_VERSION == "tumbleweed" else 13,
    "ppc64le": 16 if OS_VERSION == "tumbleweed" else 13,
}


@pytest.mark.parametrize(
    "container,size",
    [(BUSYBOX_CONTAINER, BUSYBOX_IMAGE_MAX_SIZE)],
    indirect=["container"],
)
def test_busybox_image_size(
    container, size: Dict[str, int], container_runtime
):
    """Check that the size of the busybox container is below the limits
    specified in :py:const:`BUSYBOX_IMAGE_MAX_SIZE`.

    """
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
    auto_container.connection.run_expect(
        [0],
        'for i in /bin/*; do stat -c "%N" "$i" | grep -qE "(busybox|zmore|zless|zgrep|ldd|gencat|getent|locale|iconv|localedef|ld-linux|getconf)"; done',
    )


def test_busybox_binary_works(auto_container):
    """Ensure the busybox binary works"""
    auto_container.connection.run_expect([0], "busybox")


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


def test_ca_certs_working(auto_container):
    """Checks that the mozilla certificate bundle is available to openssl."""
    auto_container.connection.exists(
        "/var/lib/ca-certificates/openssl/c90bc37d.0"
    )


@pytest.mark.parametrize(
    "container_per_test", [BUSYBOX_CONTAINER], indirect=True
)
def test_busybox_adduser(container_per_test):
    """Ensure the adduser command works and a new user can be created"""
    container_per_test.connection.run_expect([0], "adduser -D foo")
    getent_passwd = container_per_test.connection.run_expect(
        [0], "getent passwd foo"
    )
    assert "foo" in getent_passwd.stdout
    container_per_test.connection.run_expect([0], "su - foo")
