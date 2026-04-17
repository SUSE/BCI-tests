"""This module contains the tests for the AMD GPU container."""

import pytest
from pytest_container.container import ContainerData

from bci_tester.data import AMD_CONTAINERS

CONTAINER_IMAGES = AMD_CONTAINERS


@pytest.mark.parametrize(
    "container_per_test",
    AMD_CONTAINERS,
    indirect=True,
)
def test_image_content(container_per_test: ContainerData):
    """Test that ensures that required files exist in the image."""

    # check that required modules are in the correct place
    # https://github.com/ROCm/gpu-operator/blob/v1.4.1/internal/kmmmodule/kmmmodule.go#L872
    files = [
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amdkcl.ko",
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amdttm.ko",
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amdgpu.ko",
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amdxcp.ko",
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amd-sched.ko",
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amddrm_buddy.ko",
        "/opt/lib/modules/6.4.0-150700.51-default/updates/dkms/amddrm_ttm_helper.ko",
    ]

    for filename in files:
        assert container_per_test.connection.file(filename).exists
        assert container_per_test.connection.file(filename).is_file

    directories = [
        "/firmwareDir/updates/amdgpu/amdgpu/",
        "/opt/lib/modules/6.4.0-150700.51-default/kernel/",
    ]

    for filename in directories:
        assert container_per_test.connection.file(filename).exists
        assert container_per_test.connection.file(filename).is_directory
