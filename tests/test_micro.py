from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import MICRO_CONTAINER

CONTAINER_IMAGES = [
    MICRO_CONTAINER,
]

#: size limits of the micro image per architecture in MiB
MICRO_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 25,
    "aarch64": 28,
    "s390x": 25,
    "ppc64le": 33,
}


def test_micro_image_size(auto_container, container_runtime):
    """Check that the size of the micro container is below the limits from :py:const:`MICRO_IMAGE_MAX_SIZE`."""
    assert (
        container_runtime.get_image_size(auto_container.image_url_or_id)
        < MICRO_IMAGE_MAX_SIZE[LOCALHOST.system_info.arch] * 1024 * 1024
    )


def test_fat_packages_absent(auto_container):
    """Verify that the following binaries do not exist:
    - :command:`zypper`
    - :command:`grep`
    - :command:`diff`
    - :command:`sed`
    - :command:`info`
    - :command:`man`
    """
    for pkg in ("zypper", "grep", "diff", "sed", "info", "man"):
        assert not auto_container.connection.exists(pkg)


def test_rpm_absent(auto_container):
    """Ensure that rpm is not present in the micro container."""
    assert not auto_container.connection.exists(
        "rpm"
    ), "rpm must not be present in the micro container"
