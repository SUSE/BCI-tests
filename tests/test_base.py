"""Tests for the base container itself (the one that is already present on
registry.suse.com)

"""
from typing import Dict

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.fips import ALL_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import target_fips_enforced
from bci_tester.runtime_choice import DOCKER_SELECTED

#: size limits of the base container per arch in MiB
BASE_CONTAINER_MAX_SIZE: Dict[str, int] = {
    "x86_64": 120,
    "aarch64": 140,
    "ppc64le": 160,
    "s390x": 125,
}

CONTAINER_IMAGES = [BASE_CONTAINER]


def test_passwd_present(auto_container):
    """Generic test that :file:`/etc/passwd` exists"""
    assert auto_container.connection.file("/etc/passwd").exists


def test_base_size(auto_container, container_runtime):
    """Ensure that the container's size is below the limits specified in
    :py:const:`BASE_CONTAINER_MAX_SIZE`

    """
    assert (
        container_runtime.get_image_size(auto_container.image_url_or_id)
        < BASE_CONTAINER_MAX_SIZE[LOCALHOST.system_info.arch] * 1024 * 1024
    )


without_fips = pytest.mark.skipif(
    host_fips_enabled() or target_fips_enforced(),
    reason="host running in FIPS 140 mode",
)


def test_gost_digest_disable(auto_container):
    """Checks that the gost message digest is not known to openssl."""
    openssl_error_message = (
        "Invalid command 'gost'"
        if OS_VERSION == "tumbleweed"
        else "gost is not a known digest"
    )
    assert (
        openssl_error_message
        in auto_container.connection.run_expect(
            [1], "openssl gost /dev/null"
        ).stderr.strip()
    )


@without_fips
def test_openssl_hashes(auto_container):
    """If the host is not running in fips mode, then we check that all hash
    algorithms work via :command:`openssl $digest /dev/null`.

    """
    for digest in ALL_DIGESTS:
        auto_container.connection.run_expect(
            [0], f"openssl {digest} /dev/null"
        )


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
    EXPECTED_DIGEST_LIST = ALL_DIGESTS
    # gost is not supported to generate digests, but it appears in:
    # openssl list --digest-commands
    if OS_VERSION != "tumbleweed":
        EXPECTED_DIGEST_LIST += ("gost",)
    assert len(hashes) == len(EXPECTED_DIGEST_LIST)
    assert set(hashes) == set(EXPECTED_DIGEST_LIST)


#: This is the base container with additional launch arguments applied to it so
#: that docker can be launched inside the container
DIND_CONTAINER = pytest.param(
    DerivedContainer(
        base=container_from_pytest_param(BASE_CONTAINER),
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
