"""This module contains the tests for the AMD GPU container."""

import pytest
from pytest_container.container import ContainerData

from bci_tester.data import AMD_CONTAINERS
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = AMD_CONTAINERS


@pytest.mark.parametrize(
    "container_per_test",
    AMD_CONTAINERS,
    indirect=True,
)
def test_image_content(container_per_test: ContainerData):
    """Test that ensures that required files exist in the image."""

    if OS_VERSION.startswith("16.0"):
        kernel_ga = "6.12.0-160000.5"
    elif OS_VERSION.startswith("15.7"):
        kernel_ga = "6.4.0-150700.51"
    else:
        raise ValueError(f"Unknown OS_VERSION: {OS_VERSION}")

    # check that required modules are in the correct place
    # https://github.com/ROCm/gpu-operator/blob/v1.4.1/internal/kmmmodule/kmmmodule.go#L872
    files = [
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amdkcl.ko",
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amdttm.ko",
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amdgpu.ko",
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amdxcp.ko",
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amd-sched.ko",
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amddrm_buddy.ko",
        f"/opt/lib/modules/{kernel_ga}-default/updates/dkms/amddrm_ttm_helper.ko",
        "/usr/share/licenses/amdgpu-dkms-firmware/LICENSE",
    ]

    for filename in files:
        assert container_per_test.connection.file(filename).exists
        assert container_per_test.connection.file(filename).is_file

    directories = [
        "/firmwareDir/updates/amdgpu/",
        f"/opt/lib/modules/{kernel_ga}-default/kernel/",
    ]

    for filename in directories:
        assert container_per_test.connection.file(filename).exists
        assert container_per_test.connection.file(filename).is_directory
