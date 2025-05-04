"""Tests for the SLE15 kernel-module container."""

import re

import pytest
from _pytest.mark import ParameterSet
from pytest_container import DerivedContainer
from pytest_container import GitRepositoryBuild
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = [KERNEL_MODULE_CONTAINER]

pytestmark = pytest.mark.skipif(
    OS_VERSION in ("tumbleweed",),
    reason="no kernel-module containers for Tumbleweed",
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


# the commit hash and the download link for the sources need to be updated together
# there is no significance to the chosen hash, it is simple the tip of tree with the
# corresponding sources to fetch.
KMP_CONTAINER = create_kernel_test(
    r"""WORKDIR /src
RUN set -euxo pipefail; \
    curl -sf https://src.opensuse.org/pool/vhba-kmp/archive/a5848539656e86e460a43f7027c40cec49868876460bc21c7302b0f1d9e1e5ef.tar.gz | tar -xzf - ; \
    cp -a vhba-kmp/* /usr/src/packages/SOURCES; cd /usr/src/packages/SOURCES ; \
    curl -LO https://downloads.sf.net/cdemu/vhba-module-20240917.tar.xz ; \
    rpmbuild -bb vhba-kmp.spec ; \
    openssl req -new -x509 -newkey rsa:2048 -sha256 -keyout key.asc -out cert.der \
            -outform der -nodes -days 4745 -addext "extendedKeyUsage=codeSigning" \
            -subj "/CN=Donut Eat/" ; \
    modsign-repackage -c ./cert.der -k ./key.asc /usr/src/packages/RPMS/$(uname -m)/vhba-kmp-default-*.rpm ; \
    rpm -i --nodeps RPMS/$(uname -m)/vhba-kmp-default-*.rpm
""",
)


@pytest.mark.parametrize("container", [KMP_CONTAINER], indirect=True)
def test_kmp_builds(container: ContainerData) -> None:
    """Test that we can build a SUSE Kernel Module Package with signed modules."""

    assert "Donut Eat" in container.connection.check_output(
        "modinfo /lib/modules/*-default/*/vhba.ko"
    )


@pytest.mark.skipif(
    OS_VERSION in ("16.0",),
    reason="can't install additional packages yet on 16",
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
@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://dpdk.org/git/dpdk-kmods",
            repository_tag="main",
            build_command="""cd linux/igb_uio/;
                make KSRC=/usr/src/linux-obj/$(uname -m)/default""",
        ).to_pytest_param(),
    ],
    indirect=["container_git_clone"],
)
def test_igb_uio(auto_container_per_test, container_git_clone) -> None:
    """Test that the DPDK kernel module builds."""
    igb_uio_kernel_module_file = "/dpdk-kmods/linux/igb_uio/igb_uio.ko"

    auto_container_per_test.connection.check_output(
        container_git_clone.test_command
    )

    assert auto_container_per_test.connection.file(
        igb_uio_kernel_module_file
    ).exists
    modinfo_out = auto_container_per_test.connection.check_output(
        f"modinfo {igb_uio_kernel_module_file}"
    )
    assert re.search(r"^name:\s+igb_uio", modinfo_out, flags=re.MULTILINE)
