from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import MINIMAL_CONTAINER

CONTAINER_IMAGES = [
    MINIMAL_CONTAINER,
]

#: size limits of the minimal image per architecture in MiB
MINIMAL_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 46,
    "aarch64": 49,
    "s390x": 46,
    "ppc64le": 57,
}


def test_minimal_image_size(auto_container, container_runtime):
    """Check that the size of the minimal container is below the limits specified in
    :py:const:`MINIMAL_IMAGE_MAX_SIZE`.

    """
    assert (
        container_runtime.get_image_size(auto_container.image_url_or_id)
        < MINIMAL_IMAGE_MAX_SIZE[LOCALHOST.system_info.arch] * 1024 * 1024
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


def test_rpm_present(auto_container):
    """Ensure that rpm is present in the minimal container."""
    assert auto_container.connection.exists(
        "rpm"
    ), "rpm must be present in the minimal container"
