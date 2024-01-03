"""Tests for the SLE15 kernel-module container."""
import pytest
from pytest_container import container_from_pytest_param
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData

from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = [KERNEL_MODULE_CONTAINER]

pytestmark = pytest.mark.skipif(
    OS_VERSION in ("tumbleweed", "basalt"),
    reason="no kernel-module containers for Tumbleweed and Basalt",
)

_DRBD_VERSION = "9.2.7"


def create_kernel_test(containerfile: str) -> pytest.param:
    return pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(KERNEL_MODULE_CONTAINER),
            containerfile=containerfile,
        ),
        marks=KERNEL_MODULE_CONTAINER.marks,
        id=KERNEL_MODULE_CONTAINER.id,
    )


DRBD_CONTAINER = create_kernel_test(
    rf"""WORKDIR /src/
RUN zypper -n in coccinelle tar

RUN set -euxo pipefail; \
    curl -Lsf -o - https://pkg.linbit.com//downloads/drbd/9/drbd-{_DRBD_VERSION}.tar.gz | tar xzf - ; \
    cd drbd-{_DRBD_VERSION}; \
    make -C /usr/src/linux-obj/$(uname -m)/default modules M="$(pwd)/drbd" SPAAS=false
""",
)

_DPDK_VERSION = "23.07"

DPDK_CONTAINER = create_kernel_test(
    rf"""WORKDIR /src/
RUN zypper -n in meson python3-pip libnuma-devel && pip install pyelftools

RUN set -euxo pipefail; \
    curl -Lsf -o - https://fast.dpdk.org/rel/dpdk-{_DPDK_VERSION}.tar.gz | tar xzf - ; cd dpdk-{_DPDK_VERSION}; \
    meson --prefix=/usr --includedir=/usr/include/ -Ddefault_library=shared -Denable_docs=false -Db_lto=false -Dplatform="$(uname -m)" -Dcpu_instruction_set=generic -Denable_kmods=true -Dkernel_dir="/usr/src/linux-obj/$(uname -m)/default" build; \
    meson compile -C build
"""
)


@pytest.mark.parametrize("container", [DRBD_CONTAINER], indirect=True)
def test_drbd_builds(container: ContainerData) -> None:
    """Test that the DRBD kernel module builds."""
    assert container.connection.file(
        f"/src/drbd-{_DRBD_VERSION}/drbd/drbd.ko"
    ).exists


@pytest.mark.parametrize("container", [DPDK_CONTAINER], indirect=True)
def test_dpdk_builds(container: ContainerData) -> None:
    """Test that the DPDK kernel module builds."""
    assert container.connection.file(
        f"/src/dpdk-{_DPDK_VERSION}/build/kernel/linux/kni/rte_kni.ko"
    ).exists
