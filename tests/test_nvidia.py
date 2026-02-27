"""This module contains the tests for the valkey container."""

import pytest
from pytest_container import DerivedContainer
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData

from bci_tester.data import NVIDIA_CONTAINERS

CONTAINER_IMAGES = NVIDIA_CONTAINERS

NO_ENTRYPOINT_CONTAINERS = []

for param in NVIDIA_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(param)
    NO_ENTRYPOINT_CONTAINERS.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                custom_entry_point="/bin/sh",
            ),
            marks=marks,
        )
    )


@pytest.mark.parametrize(
    "container_per_test",
    NO_ENTRYPOINT_CONTAINERS,
    indirect=True,
)
def test_image_content(container_per_test: ContainerData):
    """Test that ensures that required files exist in the image."""
    version = container_per_test.inspect.config.env.get("DRIVER_VERSION")

    files = [
        "/drivers/README.md",
        "/licenses/NGC-DL-CONTAINER-LICENSE",
        f"/opt/lib/firmware/nvidia/{version}/gsp_ga10x.bin",
        f"/opt/lib/firmware/nvidia/{version}/gsp_tu10x.bin",
        "/opt/open/nvidia-drm.ko.zst",
        "/opt/open/nvidia-modeset.ko.zst",
        "/opt/open/nvidia-peermem.ko.zst",
        "/opt/open/nvidia-uvm.ko.zst",
        "/opt/open/nvidia.ko.zst",
        "/opt/proprietary/nvidia-drm.ko.zst",
        "/opt/proprietary/nvidia-modeset.ko.zst",
        "/opt/proprietary/nvidia-peermem.ko.zst",
        "/opt/proprietary/nvidia-uvm.ko.zst",
        "/opt/proprietary/nvidia.ko.zst",
        "/usr/local/bin/extract-vmlinux",
        "/usr/local/bin/nvidia-driver",
        "/usr/local/bin/nvidia-driver-selector.sh",
    ]

    for filename in files:
        assert container_per_test.connection.file(filename).exists
