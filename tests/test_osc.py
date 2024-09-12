"""Smoke tests for the osc container"""

import os.path
import re
from pathlib import Path
from typing import List
from typing import Union

import pytest
from pytest_container import DerivedContainer
from pytest_container import OciRuntimeBase
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import BindMount
from pytest_container.container import ContainerData
from pytest_container.container import ContainerLauncher
from pytest_container.container import ContainerVolume
from pytest_container.container import VolumeFlag
from pytest_container.runtime import LOCALHOST

from bci_tester.data import OSC_CONTAINERS

pytestmark = pytest.mark.skipif(
    (not LOCALHOST.package("osc").is_installed)
    or (
        "api.opensuse.org"
        not in LOCALHOST.check_output("osc config general apiurl")
    ),
    reason="osc not installed or not configured to communicate with OBS",
)

OSC_WITH_CONFIG_CTR = []
_volume_mounts: List[Union[BindMount, ContainerVolume]] = [
    BindMount(
        host_path=os.path.expanduser("~/.config/osc/oscrc"),
        container_path="/root/.config/osc/oscrc",
        flags=[
            VolumeFlag.READ_ONLY,
            VolumeFlag.SELINUX_PRIVATE,
        ],
    ),
    BindMount(
        host_path=os.path.expanduser("~/.local/state/osc/cookiejar"),
        container_path="/root/.local/state/osc/cookiejar",
    ),
]

for param in OSC_CONTAINERS:
    _ctr, _marks = container_and_marks_from_pytest_param(param)
    OSC_WITH_CONFIG_CTR.append(
        pytest.param(
            DerivedContainer(
                base=_ctr,
                extra_launch_args=["--privileged"],
                volume_mounts=_volume_mounts,
            ),
            marks=_marks,
            id=param.id,
        )
    )

CONTAINER_IMAGES = OSC_WITH_CONFIG_CTR


def test_osc_ls_factory(auto_container: ContainerData):
    """Simple smoke test for :command:`osc ls openSUSE:Factory` working."""
    assert "aaa_base" in auto_container.connection.check_output(
        "osc ls openSUSE:Factory"
    )


def test_osc_checkout(auto_container_per_test: ContainerData):
    """Try to run :command:`osc co devel:microos/slirp4netns` and check whether
    ``slirp4netns.spec`` exists.

    """
    prj, pkg = "devel:microos", "slirp4netns"
    auto_container_per_test.connection.check_output(f"osc co {prj}/{pkg}")

    assert auto_container_per_test.connection.file(
        str(
            auto_container_per_test.inspect.config.workingdir
            / prj
            / pkg
            / f"{pkg}.spec"
        )
    ).exists


def test_osc_build_rootlesskit(auto_container_per_test: ContainerData):
    """Checkout ``devel:microos/rootlesskit``, change into that directory, build
    the package and verify that the resulting binaries are valid rpms.

    """
    prj, pkg = "devel:microos", "rootlesskit"
    auto_container_per_test.connection.check_output(f"osc co {prj}/{pkg}")
    osc_build_out: str = auto_container_per_test.connection.check_output(
        f"cd {prj}/{pkg}; osc build"
    )

    rpm_count = 0

    for line in reversed(osc_build_out.strip().splitlines()):
        if line.startswith("["):
            break

        if line.startswith("/var/tmp/") and line.endswith("rpm"):
            rpm_count += 1
            assert auto_container_per_test.connection.file(line).exists
            auto_container_per_test.connection.check_output(f"rpm -q {line}")

    assert rpm_count > 0, "Must have at least one built rpm"


@pytest.mark.parametrize("ctr_image", OSC_CONTAINERS)
def test_osc_packagecache_volume(
    pytestconfig: pytest.Config,
    container_runtime: OciRuntimeBase,
    ctr_image: DerivedContainer,
    tmp_path: Path,
) -> None:
    """Test a build of ``devel:microos/rootleskit`` with the
    :file:`/var/tmp/osbuild-packagecache` directory bind mounted to the host
    into a temporary directory. Then create a new container sharing the
    package-cache, rebuild ``devel:microos/rootleskit`` and check that the
    package cache is reused.

    """
    ctr_with_volume = DerivedContainer(
        base=ctr_image,
        extra_launch_args=["--privileged"],
        volume_mounts=(
            _volume_mounts
            + [
                BindMount(
                    container_path="/var/tmp/osbuild-packagecache",
                    host_path=str(tmp_path),
                )
            ]
        ),
    )

    prj, pkg = "devel:microos", "rootlesskit"

    assert len(os.listdir(tmp_path)) == 0

    # launch the container via the launcher and not the fixture, as we cannot
    # launch two containers after another
    with ContainerLauncher.from_pytestconfig(
        ctr_with_volume, container_runtime, pytestconfig
    ) as launcher:
        launcher.launch_container()
        con = launcher.container_data.connection
        con.check_output(f"osc co {prj}/{pkg}")
        assert "100.0% cache miss." in con.check_output(
            f"cd {prj}/{pkg}; osc build"
        )

    # there should be now _something_ in the cache
    assert len(os.listdir(tmp_path)) > 0

    # and now the cache should be used
    with ContainerLauncher.from_pytestconfig(
        ctr_with_volume, container_runtime, pytestconfig
    ) as launcher:
        launcher.launch_container()
        con = launcher.container_data.connection
        con.check_output(f"osc co {prj}/{pkg}")

        cache_misses = re.search(
            r"^(?P<percent>\d+(\.\d)?)% cache miss.",
            con.check_output(f"cd {prj}/{pkg}; osc build"),
            flags=re.MULTILINE,
        )

        assert (
            cache_misses
            and cache_misses.group("percent")
            and float(cache_misses.group("percent")) < 100.0
        )
