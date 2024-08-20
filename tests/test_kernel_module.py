"""Tests for the SLE15 kernel-module container."""

import re

import pytest
from _pytest.mark import ParameterSet
from pytest_container import DerivedContainer
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = [KERNEL_MODULE_CONTAINER]

pytestmark = pytest.mark.skipif(
    OS_VERSION in ("tumbleweed", "basalt"),
    reason="no kernel-module containers for Tumbleweed and Basalt",
)

_DRBD_VERSION = "9.2.11"


def create_kernel_test(containerfile: str) -> ParameterSet:
    return pytest.param(
        DerivedContainer(
            base=container_and_marks_from_pytest_param(
                KERNEL_MODULE_CONTAINER
            )[0],
            containerfile=containerfile,
        ),
        marks=KERNEL_MODULE_CONTAINER.marks,
        id=KERNEL_MODULE_CONTAINER.id,
    )


DRBD_CONTAINER = create_kernel_test(
    rf"""WORKDIR /src/
RUN zypper -n in coccinelle tar

RUN set -euxo pipefail; \
    curl -Lsf -o - https://pkg.linbit.com/downloads/drbd/9/drbd-{_DRBD_VERSION}.tar.gz | tar xzf - ; \
    cd drbd-{_DRBD_VERSION}; \
    make -C drbd all KDIR=/usr/src/linux-obj/$(uname -m)/default
""",
)

IGB_UIO_CONTAINER = create_kernel_test(
    r"""WORKDIR /src/
RUN set -euxo pipefail; \
    zypper -n in git; \
    zypper -n clean;
RUN set -euxo pipefail; \
    git clone https://dpdk.org/git/dpdk-kmods; \
    cd dpdk-kmods/linux/igb_uio/; \
    make KSRC=/usr/src/linux-obj/$(uname -m)/default
"""
)


@pytest.mark.parametrize("container", [DRBD_CONTAINER], indirect=True)
def test_drbd_builds(container: ContainerData) -> None:
    """Test that the DRBD kernel module builds."""
    drbd_kernel_module_file = (
        f"/src/drbd-{_DRBD_VERSION}/drbd/build-current/drbd.ko"
    )

    assert container.connection.file(drbd_kernel_module_file).exists

    modinfo_out = container.connection.check_output(
        f"modinfo {drbd_kernel_module_file}"
    )
    assert re.search(r"^name:\s+drbd", modinfo_out, flags=re.MULTILINE)
    assert re.search(
        rf"^version:\s+{_DRBD_VERSION}", modinfo_out, flags=re.MULTILINE
    )


@pytest.mark.skipif(
    LOCALHOST.system_info.arch not in ("x86_64", "aarch64", "ppc64le"),
    reason="DPDK is not supported on this architecture",
)
@pytest.mark.parametrize("container", [IGB_UIO_CONTAINER], indirect=True)
def test_igb_uio(container: ContainerData) -> None:
    """Test that the DPDK kernel module builds."""
    igb_uio_kernel_module_file = "/src/dpdk-kmods/linux/igb_uio/igb_uio.ko"

    assert container.connection.file(igb_uio_kernel_module_file).exists
    modinfo_out = container.connection.check_output(
        f"modinfo {igb_uio_kernel_module_file}"
    )
    assert re.search(r"^name:\s+igb_uio", modinfo_out, flags=re.MULTILINE)
