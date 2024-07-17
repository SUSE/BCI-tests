"""Tests for the base container itself (the one that is already present on
registry.suse.com)

"""

from typing import Dict

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import LTSS_BASE_CONTAINERS
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import OS_VERSION
from bci_tester.fips import ALL_DIGESTS
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import target_fips_enforced
from bci_tester.runtime_choice import DOCKER_SELECTED
from bci_tester.runtime_choice import PODMAN_SELECTED
from tests.test_fips import openssl_fips_hashes_test_fnct

CONTAINER_IMAGES = [
    BASE_CONTAINER,
    *LTSS_BASE_CONTAINERS,
    *LTSS_BASE_FIPS_CONTAINERS,
]


def test_passwd_present(auto_container):
    """Generic test that :file:`/etc/passwd` exists"""
    assert auto_container.connection.file("/etc/passwd").exists


@pytest.mark.skipif(
    OS_VERSION not in ("tumbleweed",),
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
    not PODMAN_SELECTED,
    reason="docker size reporting is dependant on underlying filesystem",
)
def test_base_size(auto_container: ContainerData, container_runtime):
    """Ensure that the container's size is below the limits specified in
    :py:const:`base_container_max_size`

    """

    # the FIPS container is bigger too than the 15 SP3 base image
    is_fips_ctr = (
        auto_container.container.baseurl
        and auto_container.container.baseurl.rpartition("/")[2].startswith(
            "bci-base-fips"
        )
    )

    #: size limits of the base container per arch in MiB
    if is_fips_ctr:
        # SP4+ is a lot larger as it pulls in python3 and
        # the FIPS crypto policy scripts
        base_container_max_size: Dict[str, int] = {
            "x86_64": 130 if OS_VERSION in ("15.3",) else 169,
        }
    elif OS_VERSION in ("basalt", "tumbleweed"):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 100,
            "aarch64": 126,
            "ppc64le": 138,
            "s390x": 99,
        }
    # 15.5/15.6 are hopefully only temporary large due to PED-5014
    elif OS_VERSION in ("15.6",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 131,
            "aarch64": 150,
            "ppc64le": 173,
            "s390x": 131,
        }
    elif OS_VERSION in ("15.5",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 122,
            "aarch64": 142,
            "ppc64le": 164,
            "s390x": 126,
        }
    elif OS_VERSION in ("15.4",):
        base_container_max_size: Dict[str, int] = {
            "x86_64": 118,
            "aarch64": 135,
            "ppc64le": 156,
            "s390x": 122,
        }
    else:
        base_container_max_size: Dict[str, int] = {
            "x86_64": 120,
            "aarch64": 140,
            "ppc64le": 160,
            "s390x": 125,
        }
    container_size = container_runtime.get_image_size(
        auto_container.image_url_or_id
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
        if OS_VERSION in ("basalt", "tumbleweed", "15.6")
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
    [c for c in CONTAINER_IMAGES if c not in LTSS_BASE_FIPS_CONTAINERS],
    indirect=True,
)
def test_openssl_hashes(container):
    """If the host is not running in fips mode, then we check that all hash
    algorithms work via :command:`openssl $digest /dev/null`.

    """
    for digest in ALL_DIGESTS:
        container.connection.run_expect([0], f"openssl {digest} /dev/null")


@pytest.mark.parametrize(
    "container_per_test", [*LTSS_BASE_FIPS_CONTAINERS], indirect=True
)
def test_openssl_fips_hashes(container_per_test):
    openssl_fips_hashes_test_fnct(container_per_test)


def test_all_openssl_hashes_known(auto_container):
    """Sanity test that all openssl digests are saved in
    :py:const:`bci_tester.fips.ALL_DIGESTS`.

    """
    hashes = (
        auto_container.connection.run_expect(
            [0], "openssl list --digest-commands"
        )
        .stdout.strip()
        .split()
    )
    expected_digest_list = ALL_DIGESTS
    # openssl-3 reduces the listed digests in FIPS mode, openssl 1.x does not

    if OS_VERSION in ("basalt", "tumbleweed", "15.6"):
        if host_fips_enabled() or target_fips_enforced():
            expected_digest_list = FIPS_DIGESTS

    # gost is not supported to generate digests, but it appears in:
    # openssl list --digest-commands
    if OS_VERSION not in ("basalt", "tumbleweed", "15.6"):
        expected_digest_list += ("gost",)
    assert len(hashes) == len(expected_digest_list)
    assert set(hashes) == set(expected_digest_list)


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
