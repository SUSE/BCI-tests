"""This module contains the tests for the kiwi container, the image with kiwi package & dependencies pre-installed."""

import pytest
from pytest_container import DerivedContainer
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat

from bci_tester.data import KIWI_CONTAINERS
from bci_tester.runtime_choice import DOCKER_SELECTED

CONTAINER_IMAGES = KIWI_CONTAINERS

KIWI_CONTAINER_EXTENDED = []

CONTAINERFILE_KIWI_EXTENDED = """
RUN set -euo pipefail; \
zypper -n in --no-recommends git-core; \
zypper -n clean; \
rm -rf /var/log/{lastlog,tallylog,zypper.log,zypp/history,YaST2}

RUN git clone https://github.com/OSInside/kiwi
"""

for kiwi_ctr in KIWI_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(kiwi_ctr)
    KIWI_CONTAINER_EXTENDED.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                containerfile=CONTAINERFILE_KIWI_EXTENDED,
                image_format=ImageFormat.DOCKER,
                extra_launch_args=["--privileged", "-v", "/dev:/dev"],
            ),
            marks=marks,
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


# Disabling this test with `podman` as it mounts the newly created iso image (by kiwi)
# on a `/dev/loop*` device, which needs a rootful container for `root:disk` ownership.
# In rootless mode, `/dev/loop*` devices are owned by `nobody:nobody`,
# causing `losetup -f --show /tmp/myimage/kiwi-test-image-disk.x86_64-1.15.3.raw` to fail with "Permission denied".
#
# Also ref: https://github.com/containers/podman/issues/17715#issuecomment-1460227771
# Mounting a loop device in rootless mode is not allowed by the kernel.
@pytest.mark.skipif(
    not DOCKER_SELECTED,
    reason="https://github.com/containers/podman/issues/17715#issuecomment-1460227771",
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

    assert "root:" in container_per_test.connection.check_output(
        "stat -c '%U:%G' /dev/loop1"
    )

    assert container_per_test.connection.file("kiwi/build-tests").exists

    kiwi_cmd = "kiwi-ng system build --description kiwi/build-tests/x86/leap/test-image-disk --set-repo obs://openSUSE:Leap:15.5/standard --target-dir /tmp/myimage"
    assert container_per_test.connection.run_expect([0], kiwi_cmd)

    assert container_per_test.connection.run_expect(
        [0], "kiwi-ng result list --target-dir=/tmp/myimage/"
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
        assert container_per_test.connection.run_expect([0], command)
