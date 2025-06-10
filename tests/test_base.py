"""Tests for the base container itself (the one that is already present on
registry.suse.com)

"""

from pathlib import Path
from typing import Dict

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import BindMount
from pytest_container.container import ContainerData
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BASE_FIPS_CONTAINERS
from bci_tester.data import LTSS_BASE_CONTAINERS
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import OS_VERSION
from bci_tester.data import TARGET
from bci_tester.data import ZYPP_CREDENTIALS_DIR
from bci_tester.fips import ALL_DIGESTS
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import target_fips_enforced
from bci_tester.runtime_choice import DOCKER_SELECTED
from bci_tester.runtime_choice import PODMAN_SELECTED
from tests.test_fips import digest_xoflen
from tests.test_fips import openssl_fips_hashes_test_fnct

CONTAINER_IMAGES = [
    BASE_CONTAINER,
    *BASE_FIPS_CONTAINERS,
    *LTSS_BASE_CONTAINERS,
    *LTSS_BASE_FIPS_CONTAINERS,
]

DOCKERFILE = """WORKDIR /src/
COPY tests/files/fips-test.c /src/
"""

FIPS_TESTER_IMAGES = []
for param in [*LTSS_BASE_FIPS_CONTAINERS, *BASE_FIPS_CONTAINERS] + (
    [BASE_CONTAINER] if TARGET in ("dso",) else []
):
    ctr, marks = container_and_marks_from_pytest_param(param)
    kwargs = {
        "base": ctr,
        "extra_environment_variables": ctr.extra_environment_variables,
        "extra_launch_args": ctr.extra_launch_args,
        "custom_entry_point": ctr.custom_entry_point,
        "volume_mounts": (
            [
                BindMount(
                    ZYPP_CREDENTIALS_DIR,
                    host_path=ZYPP_CREDENTIALS_DIR,
                    flags=[],
                )
            ]
            if Path(ZYPP_CREDENTIALS_DIR).exists()
            else []
        ),
    }
    tester_ctr = DerivedContainer(containerfile=DOCKERFILE, **kwargs)
    FIPS_TESTER_IMAGES.append(
        pytest.param(tester_ctr, marks=marks, id=param.id)
    )


def test_passwd_present(auto_container):
    """Generic test that :file:`/etc/passwd` exists"""
    assert auto_container.connection.file("/etc/passwd").exists


@pytest.mark.skipif(
    OS_VERSION not in ("tumbleweed", "16.0"),
    reason="requires gconv modules",
)
def test_iconv_working(auto_container):
    """Generic test iconv works for UTF8 and ISO-8859-15 locale"""
    assert (
        auto_container.connection.check_output(
            "echo -n 'SüSE' | iconv -f UTF8 -t ISO_8859-15 | wc -c"
        )
        == "4"
    )


@pytest.mark.skipif(
    OS_VERSION in ("15.3", "15.4", "15.5"),
    reason="unfixed in LTSS codestreams",
)
def test_group_nobody_working(auto_container):
    """Test that nobody group is available in the container (bsc#1212118)."""
    assert auto_container.connection.check_output("getent group nobody")


@pytest.mark.skipif(
    not PODMAN_SELECTED,
    reason="docker size reporting is dependent on underlying filesystem",
)
@pytest.mark.parametrize(
    "container",
    [c for c in CONTAINER_IMAGES if c not in BASE_FIPS_CONTAINERS],
    indirect=True,
)
def test_base_size(container: ContainerData, container_runtime):
    """Ensure that the container's size is below the limits specified in
    :py:const:`base_container_max_size`

    """
    # the FIPS container is bigger too than the 15 SP3 base image
    is_fips_ctr = (
        container.container.baseurl
        and container.container.baseurl.rpartition("/")[2].startswith(
            "bci-base-fips"
        )
        or TARGET in ("dso",)
    )

    # Size limits determined by running
    # img=<locationtoimage>;  for arch in x86_64 aarch64 ppc64le s390x; do
    #   podman pull --arch=$arch $img > /dev/null; echo -n "## $arch: ";
    #   echo "$(podman  image inspect -f '{{.Size}}' $img )"/1024/1024 | bc -l;
    # done
    #: size limits of the base container per arch in MiB
    if is_fips_ctr:
        # SP4+ is a lot larger as it pulls in python3 and
        # the FIPS crypto policy scripts
        base_container_max_size: Dict[str, int] = {
            "x86_64": 130 if OS_VERSION in ("15.3",) else 169,
        }
        if TARGET in ("dso",):
            # the dso container is larger than the bci-base-fips container
            base_container_max_size["x86_64"] += 10
    elif OS_VERSION in ("tumbleweed",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 99,
            "aarch64": 115,
            "ppc64le": 126,
            "s390x": 91,
        }
    elif OS_VERSION in ("16.0",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 95,
            "aarch64": 100,
            "ppc64le": 114,
            "s390x": 92,
        }
    elif OS_VERSION in ("15.7",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 121,
            "aarch64": 135,
            "ppc64le": 158,
            "s390x": 122,
        }
    elif OS_VERSION in ("15.6",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 120,
            "aarch64": 134,
            "ppc64le": 155,
            "s390x": 121,
        }
    elif OS_VERSION in ("15.5",):
        # pick the sizes from sles15-ltss-image which is larger than sles15-ltsss
        base_container_max_size: Dict[str, int] = {
            "x86_64": 126,
            "aarch64": 146,
            "ppc64le": 170,
            "s390x": 130,
        }
    elif OS_VERSION in ("15.4",):
        # pick the sizes from sles15-ltss-image which is larger than sles15-ltsss
        base_container_max_size: Dict[str, int] = {
            "x86_64": 121,
            "aarch64": 142,
            "ppc64le": 162,
            "s390x": 125,
        }
    else:
        base_container_max_size: Dict[str, int] = {
            "x86_64": 120,
            "aarch64": 140,
            "ppc64le": 160,
            "s390x": 125,
        }
    container_size = container_runtime.get_image_size(
        container.image_url_or_id
    ) // (1024 * 1024)
    max_container_size = base_container_max_size[LOCALHOST.system_info.arch]
    assert container_size <= max_container_size, (
        f"Base container size is {container_size} MiB for {LOCALHOST.system_info.arch} "
        f"(expected max of {base_container_max_size[LOCALHOST.system_info.arch]} MiB)"
    )


without_fips = pytest.mark.skipif(
    host_fips_enabled() or target_fips_enforced(),
    reason="host running in FIPS 140 mode",
)


def test_gost_digest_disable(auto_container):
    """Checks that the gost message digest is not known to openssl."""
    openssl_error_message = (
        "Invalid command 'gost'"
        if OS_VERSION not in ("15.3", "15.4", "15.5")
        else "gost is not a known digest"
    )
    assert (
        openssl_error_message
        in auto_container.connection.run_expect(
            [1], "openssl gost /dev/null"
        ).stderr.strip()
    )


@without_fips
@pytest.mark.parametrize(
    "container",
    [
        c
        for c in CONTAINER_IMAGES
        if c not in (*LTSS_BASE_FIPS_CONTAINERS, *BASE_FIPS_CONTAINERS)
    ],
    indirect=True,
)
def test_openssl_hashes(container):
    """If the host is not running in fips mode, then we check that all hash
    algorithms work via :command:`openssl $digest /dev/null`.

    """
    for digest in ALL_DIGESTS:
        container.connection.run_expect(
            [0], f"openssl {digest}{digest_xoflen(digest)} /dev/null"
        )


@pytest.mark.parametrize(
    "container_per_test", FIPS_TESTER_IMAGES, indirect=True
)
def test_openssl_fips_hashes(container_per_test):
    """Check that all FIPS allowed hashes perform correctly."""
    openssl_fips_hashes_test_fnct(container_per_test)


def test_all_openssl_hashes_known(auto_container):
    """Sanity test that all openssl digests are saved in
    :py:const:`bci_tester.fips.ALL_DIGESTS`.

    """
    fips_mode: bool = (
        auto_container.connection.check_output(
            "echo ${OPENSSL_FORCE_FIPS_MODE:-0}"
        ).strip()
        == "1"
    )
    hashes = (
        auto_container.connection.check_output(
            "openssl list --digest-commands"
        )
        .strip()
        .split()
    )
    expected_digest_list = ALL_DIGESTS

    # openssl-3 reduces the listed digests in FIPS mode, openssl 1.x does not
    if OS_VERSION not in ("15.3", "15.4", "15.5"):
        if host_fips_enabled() or target_fips_enforced() or fips_mode:
            expected_digest_list = FIPS_DIGESTS

    # gost is not supported to generate digests, but it appears in:
    # openssl list --digest-commands
    if OS_VERSION in ("15.3", "15.4", "15.5"):
        expected_digest_list += ("gost",)

    assert set(hashes) == set(expected_digest_list), (
        f"openssl list --digest-commands returned {hashes} but expected {expected_digest_list}"
    )


#: This is the base container with additional launch arguments applied to it so
#: that docker can be launched inside the container
DIND_CONTAINER = pytest.param(
    DerivedContainer(
        base=container_and_marks_from_pytest_param(BASE_CONTAINER)[0],
        **{
            x: getattr(BASE_CONTAINER.values[0], x)
            for x in BASE_CONTAINER.values[0].__dict__
            if x not in ("extra_launch_args", "base")
        },
        extra_launch_args=[
            "--privileged=true",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
        ],
    ),
)


@pytest.mark.parametrize("container_per_test", [DIND_CONTAINER], indirect=True)
@pytest.mark.xfail(
    OS_VERSION in ("16.0",),
    reason="SLE BCI repository not yet available",
)
@pytest.mark.skipif(
    not DOCKER_SELECTED,
    reason="Docker in docker can only be tested when using the docker runtime",
)
def test_dind(container_per_test):
    """Check that we can install :command:`docker` in the container and launch the
    latest Tumbleweed container inside it.

    This requires additional settings for the docker command line (see
    :py:const:`DIND_CONTAINER`).

    """
    container_per_test.connection.run_expect([0], "zypper -n in docker")
    container_per_test.connection.run_expect([0], "docker ps")
    res = container_per_test.connection.run_expect(
        [0],
        "docker run --rm registry.opensuse.org/opensuse/tumbleweed:latest "
        "/usr/bin/ls",
    )
    assert "etc" in res.stdout
