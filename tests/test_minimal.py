"""Tests for the minimal BCI container (the container without zypper but with rpm)."""

from typing import Dict

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.runtime_choice import PODMAN_SELECTED


@pytest.mark.skipif(
    not PODMAN_SELECTED,
    reason="docker size reporting is dependent on underlying filesystem",
)
@pytest.mark.parametrize("container", [MINIMAL_CONTAINER], indirect=True)
def test_minimal_image_size(container, container_runtime):
    """Check that the size of the minimal container is below the limits specified in
    :py:const:`SLE_MINIMAL_IMAGE_MAX_SIZE`.

    """
    if OS_VERSION in ("tumbleweed",):
        minimal_container_max_size: Dict[str, int] = {
            "aarch64": 51,
            "ppc64le": 74,
            "s390x": 36,
            "x86_64": 42,
        }
    elif OS_VERSION in ("16.0",):
        minimal_container_max_size: Dict[str, int] = {
            "aarch64": 38,
            "ppc64le": 44,
            "s390x": 34,
            "x86_64": 35,
        }
    else:
        minimal_container_max_size: Dict[str, int] = {
            "x86_64": 48,
            "aarch64": 50,
            "s390x": 48,
            "ppc64le": 58,
        }

    container_size = container_runtime.get_image_size(
        container.image_url_or_id
    ) // (1024 * 1024)
    if container_size > minimal_container_max_size[LOCALHOST.system_info.arch]:
        if OS_VERSION in ("tumbleweed",):
            pytest.xfail(
                "Tumbleweed Minimal image exceeds limit (boo#1236736)"
            )
        else:
            pytest.fail(
                f"Container size {container_size} exceeds {minimal_container_max_size[LOCALHOST.system_info.arch]} MiB"
            )


@pytest.mark.skipif(
    not PODMAN_SELECTED,
    reason="docker size reporting is dependent on underlying filesystem",
)
@pytest.mark.parametrize("container", [MICRO_CONTAINER], indirect=True)
def test_micro_image_size(container, container_runtime):
    """Check that the size of the micro container is below the limits specified in
    :py:const:`SLE_MICRO_IMAGE_MAX_SIZE`.

    """

    if OS_VERSION in ("tumbleweed",):
        size: Dict[str, int] = {
            "x86_64": 30,
            "aarch64": 38,
            "s390x": 28,
            "ppc64le": 42,
        }
    elif OS_VERSION in ("16.0",):
        size: Dict[str, int] = {
            "x86_64": 30,
            "aarch64": 38,
            "s390x": 28,
            "ppc64le": 42,
        }
    else:
        size: Dict[str, int] = {
            "x86_64": 25,
            "aarch64": 28,
            "s390x": 25,
            "ppc64le": 33,
        }

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
    assert not container.connection.exists("rpm"), (
        "rpm must not be present in the micro container"
    )


@pytest.mark.parametrize(
    "container", [MINIMAL_CONTAINER], indirect=["container"]
)
def test_rpm_present_in_minimal(container):
    """Ensure that rpm is present in the minimal container."""
    assert container.connection.exists("rpm"), (
        "rpm must be present in the minimal container"
    )
