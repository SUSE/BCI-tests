"""This module contains the tests for the valkey container."""

import pytest
from pytest_container import DerivedContainer
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

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
        "/usr/local/bin/extract-vmlinux",
        "/usr/local/bin/nvidia-driver",
        "/usr/local/bin/nvidia-driver-selector.sh",
    ]

    if LOCALHOST.system_info.arch in ("aarch64",):
        ### TODO why are those uncompressed?
        files += [
            "/opt/open/nvidia-drm.ko",
            "/opt/open/nvidia-modeset.ko",
            "/opt/open/nvidia-peermem.ko",
            "/opt/open/nvidia-uvm.ko",
            "/opt/open/nvidia.ko",
            "/opt/proprietary/nvidia-drm.ko",
            "/opt/proprietary/nvidia-modeset.ko",
            "/opt/proprietary/nvidia-peermem.ko",
            "/opt/proprietary/nvidia-uvm.ko",
            "/opt/proprietary/nvidia.ko",
        ]
    elif LOCALHOST.system_info.arch in ("x86_64",):
        files += [
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
        ]

    for filename in files:
        assert container_per_test.connection.file(filename).exists
