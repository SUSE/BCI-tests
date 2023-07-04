"""Test module performing simple smoke tests for the busybox container image."""
from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import create_container_version_mark


CONTAINER_IMAGES = [BUSYBOX_CONTAINER]

pytestmark = create_container_version_mark(["15.4", "15.5", "tumbleweed"])


def test_busybox_provides_sh(auto_container):
    """Check that /bin/sh is coming from busybox and not from bash."""
    assert (
        "BusyBox"
        in auto_container.connection.run_expect([0], "sh --help").stderr
    )


#: size limits of the micro image per architecture in MiB
BUSYBOX_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 14,
    "aarch64": 14,
    "s390x": 14,
    "ppc64le": 14,
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
    assert (
        container_runtime.get_image_size(container.image_url_or_id)
        < size[LOCALHOST.system_info.arch] * 1024 * 1024
    )


def test_busybox_links(auto_container):
    """Ensure all binaries in :file:`/bin` are links to :file:`/usr/bin/busybox`."""
    auto_container.connection.run_expect(
        [0],
        'for i in /bin/*; do stat -c "%N" "$i" | grep "/usr/bin/busybox"; done',
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
    assert "root" in auto_container.connection.run_expect([0], "ps").stdout


def test_base32_64(auto_container):
    """Ensure the base32 and base64 commands are returning the correct result for a given "test" string"""
    assert (
        "ORSXG5AK"
        in auto_container.connection.run_expect(
            [0], "echo test | base32"
        ).stdout
    )
    assert (
        "dGVzdAo="
        in auto_container.connection.run_expect(
            [0], "echo test | base64"
        ).stdout
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
