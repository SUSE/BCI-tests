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

_DPDK_VERSION = "23.07"

_DPDK_MESON_SETUP = "meson python3-pip"
if OS_VERSION in ("15.6",):
    _DPDK_MESON_SETUP = "meson python311-pip"

DPDK_CONTAINER = create_kernel_test(
    rf"""WORKDIR /src/
RUN zypper -n in libnuma-devel {_DPDK_MESON_SETUP} && pip install pyelftools

RUN set -euxo pipefail; \
    curl -Lsf -o - https://fast.dpdk.org/rel/dpdk-{_DPDK_VERSION}.tar.gz | tar xzf - ; cd dpdk-{_DPDK_VERSION}; \
    meson --prefix=/usr --includedir=/usr/include/ -Ddefault_library=shared -Denable_docs=false -Db_lto=false -Dplatform="generic" -Dcpu_instruction_set=generic -Denable_kmods=true -Dkernel_dir="/usr/src/linux-obj/$(uname -m)/default" build; \
    meson compile -C build
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
@pytest.mark.parametrize("container", [DPDK_CONTAINER], indirect=True)
def test_dpdk_builds(container: ContainerData) -> None:
    """Test that the DPDK kernel module builds."""
    assert container.connection.file(
        f"/src/dpdk-{_DPDK_VERSION}/build/kernel/linux/kni/rte_kni.ko"
    ).exists
