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
            "aarch64": 63,
            "ppc64le": 58,
            "s390x": 41,
            "x86_64": 49,
        }
    elif OS_VERSION in ("16.0",):
        minimal_container_max_size: Dict[str, int] = {
            "aarch64": 38,
            "ppc64le": 45,
            "s390x": 35,
            "x86_64": 36,
        }
    else:
        minimal_container_max_size: Dict[str, int] = {
            "x86_64": 49,
            "aarch64": 51,
            "s390x": 49,
            "ppc64le": 59,
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
                "Container size f{container_size} exceeds f{minimal_container_max_size[LOCALHOST.system_info.arch]} MiB"
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
            "x86_64": 34,
            "aarch64": 42,
            "s390x": 28,
            "ppc64le": 41,
        }
    else:
        size = {
            "x86_64": 26,
            "aarch64": 28,
            "s390x": 26,
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
    "container", [MICRO_CONTAINER, MINIMAL_CONTAINER], indirect=True
)
def test_ca_certs_working(container):
    """Checks that the mozilla certificate bundle is available to openssl."""
    container.connection.exists("/var/lib/ca-certificates/openssl/c90bc37d.0")


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
