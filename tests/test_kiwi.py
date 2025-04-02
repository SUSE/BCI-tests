"""This module contains the tests for the kiwi container, the image with kiwi package & dependencies pre-installed."""

import os

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat
from pytest_container.runtime import LOCALHOST

from bci_tester.data import KIWI_CONTAINERS
from bci_tester.fips import host_fips_enabled
from bci_tester.runtime_choice import PODMAN_SELECTED
from bci_tester.selinux import selinux_status

CONTAINER_IMAGES = KIWI_CONTAINERS

KIWI_CONTAINER_EXTENDED = []

CONTAINERFILE_KIWI_EXTENDED = """
RUN curl -Lsf -o - https://github.com/OSInside/kiwi/archive/refs/heads/master.tar.gz | tar --no-same-permissions --no-same-owner -xzf - | true
"""

for ctr in KIWI_CONTAINERS:
    KIWI_CONTAINER_EXTENDED.append(
        DerivedContainer(
            base=ctr,
            containerfile=CONTAINERFILE_KIWI_EXTENDED,
            image_format=ImageFormat.DOCKER,
            extra_launch_args=["--privileged", "-v", "/dev:/dev"],
        )
    )


def test_kiwi_installation(auto_container):
    """check if kiwi package is installed inside the container"""
    assert (
        "KIWI (next generation) version"
        in auto_container.connection.check_output("kiwi --version")
    )

    assert (
        "KIWI (next generation) version"
        in auto_container.connection.check_output("kiwi-ng --version")
    )


@pytest.mark.skipif(
    LOCALHOST.system_info.arch != "x86_64",
    reason="test is atm x86_64 specific",
)
@pytest.mark.skipif(
    host_fips_enabled(),
    reason="https://github.com/OSInside/kiwi/issues/2696",
)
@pytest.mark.skipif(
    PODMAN_SELECTED and os.geteuid() != 0,
    # https://github.com/containers/podman/issues/17715#issuecomment-1460227771
    reason="PODMAN requires root privileges for kiwi tests",
)
@pytest.mark.parametrize(
    "container_per_test", KIWI_CONTAINER_EXTENDED, indirect=True
)
def test_kiwi_create_image(
    container_per_test: ContainerData,
) -> None:
    """Testing kiwi installation as per https://osinside.github.io/kiwi/quickstart.html"""

    assert (
        "KIWI (next generation) version"
        in container_per_test.connection.check_output("kiwi-ng --version")
    )

    assert container_per_test.connection.file("kiwi-main/build-tests").exists

    kiwi_cmd = "kiwi-ng system build --description kiwi-main/build-tests/x86/leap/test-image-disk --set-repo obs://openSUSE:Leap:15.6/standard --target-dir /tmp/myimage"
    res = container_per_test.connection.run_expect([0, 1], kiwi_cmd)
    if res.rc == 1 and selinux_status() == "enforcing":
        pytest.xfail(
            "kiwi container fails to build an image on hosts in SELinux enforcing mode"
        )

    container_per_test.connection.check_output(
        "kiwi-ng result list --target-dir=/tmp/myimage/"
    )

    result_files = [
        "/tmp/myimage/kiwi-test-image-disk.x86_64-*.raw",
        "/tmp/myimage/kiwi-test-image-disk.x86_64-*.changes",
        "/tmp/myimage/kiwi-test-image-disk.x86_64-*.packages",
        "/tmp/myimage/kiwi-test-image-disk.x86_64-*.verified",
        "/tmp/myimage/kiwi-test-image-disk.x86_64-*.install.iso",
    ]
    for file_path in result_files:
        command = f"ls {file_path}"
        container_per_test.connection.check_output(command)
