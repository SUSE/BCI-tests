"""Tests for the minimal BCI container (the container without zypper but with rpm)."""

from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import OS_VERSION

#: size limits of the minimal image per architecture in MiB
SLE_MINIMAL_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 49,
    "aarch64": 51,
    "s390x": 49,
    "ppc64le": 59,
}

TW_MINIMAL_IMAGE_MAX_SIZE: Dict[str, int] = {
    "aarch64": 65,
    "ppc64le": 58,
    "s390x": 41,
    "x86_64": 49,
}

#: size limits of the micro image per architecture in MiB
SLE_MICRO_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 26,
    "aarch64": 28,
    "s390x": 26,
    "ppc64le": 33,
}

TW_MICRO_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 34,
    "aarch64": 42,
    "s390x": 28,
    "ppc64le": 41,
}


@pytest.mark.parametrize("container", [MINIMAL_CONTAINER], indirect=True)
def test_minimal_image_size(container, container_runtime):
    """Check that the size of the minimal container is below the limits specified in
    :py:const:`SLE_MINIMAL_IMAGE_MAX_SIZE`.

    """
    size = (
        TW_MINIMAL_IMAGE_MAX_SIZE
        if OS_VERSION == "tumbleweed"
        else SLE_MINIMAL_IMAGE_MAX_SIZE
    )
    container_size = container_runtime.get_image_size(
        container.image_url_or_id
    ) // (1024 * 1024)
    assert container_size <= size[LOCALHOST.system_info.arch]


@pytest.mark.parametrize("container", [MICRO_CONTAINER], indirect=True)
def test_micro_image_size(container, container_runtime):
    """Check that the size of the micro container is below the limits specified in
    :py:const:`SLE_MICRO_IMAGE_MAX_SIZE`.

    """

    size = (
        TW_MICRO_IMAGE_MAX_SIZE
        if OS_VERSION == "tumbleweed"
        else SLE_MICRO_IMAGE_MAX_SIZE
    )
    container_size = container_runtime.get_image_size(
        container.image_url_or_id
    ) // (1024 * 1024)
    assert container_size <= size[LOCALHOST.system_info.arch]


@pytest.mark.parametrize(
    "container", [MICRO_CONTAINER, MINIMAL_CONTAINER], indirect=True
)
def test_fat_packages_absent(container):
    """Verify that the following binaries do not exist:
    - :command:`zypper`
    - :command:`grep`
    - :command:`diff`
    - :command:`sed`
    - :command:`info`
    - :command:`man`
    """
    for pkg in ("zypper", "grep", "diff", "sed", "info", "man"):
        assert not container.connection.exists(pkg)


@pytest.mark.parametrize(
    "container", [MICRO_CONTAINER], indirect=["container"]
)
def test_rpm_absent_in_micro(container):
    """Ensure that rpm is not present in the micro container."""
    assert not container.connection.exists(
        "rpm"
    ), "rpm must not be present in the micro container"


@pytest.mark.parametrize(
    "container", [MINIMAL_CONTAINER], indirect=["container"]
)
def test_rpm_present_in_micro(container):
    """Ensure that rpm is present in the minimal container."""
    assert container.connection.exists(
        "rpm"
    ), "rpm must be present in the minimal container"
