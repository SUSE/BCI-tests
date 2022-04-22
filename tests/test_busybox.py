"""Test module performing simple smoke tests for the busybox container image."""
from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import create_container_version_mark


CONTAINER_IMAGES = [BUSYBOX_CONTAINER]

pytestmark = create_container_version_mark(["15.4"])


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


@pytest.mark.parametrize(
    "container_per_test", [BUSYBOX_CONTAINER], indirect=True
)
def test_busybox_adduser(container_per_test):
    container_per_test.connection.run_expect([0], "adduser -D foo")
    getent_passwd = container_per_test.connection.run_expect(
        [0], "getent passwd foo"
    )
    assert "foo" in getent_passwd.stdout
    container_per_test.connection.run_expect([0], "su - foo")
