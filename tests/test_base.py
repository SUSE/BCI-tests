"""Tests for the base container itself (the one that is already present on
registry.suse.com)

"""
import re
from typing import Dict

import pytest
from pytest_container import DerivedContainer
from pytest_container import GitRepositoryBuild
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BASE_CONTAINER
from bci_tester.fips import ALL_DIGESTS
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import NONFIPS_DIGESTS
from bci_tester.runtime_choice import DOCKER_SELECTED

#: size limits of the base container per arch in MiB
BASE_CONTAINER_MAX_SIZE: Dict[str, int] = {
    "x86_64": 120,
    "aarch64": 135,
    "ppc64le": 160,
    "s390x": 120,
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


with_fips = pytest.mark.skipif(
    not host_fips_enabled(), reason="host not running in FIPS 140 mode"
)
without_fips = pytest.mark.skipif(
    host_fips_enabled(), reason="host running in FIPS 140 mode"
)


@with_fips
def test_openssl_fips_hashes(auto_container):
    """If the host is running in FIPS mode, then we check that all fips certified
    hash algorithms can be invoked via :command:`openssl $digest /dev/null` and
    all non-fips hash algorithms fail.

    """
    for md in NONFIPS_DIGESTS:
        cmd = auto_container.connection.run(f"openssl {md} /dev/null")
        assert cmd.rc != 0
        assert "not a known digest" in cmd.stderr

    for md in FIPS_DIGESTS:
        auto_container.connection.run_expect([0], f"openssl {md} /dev/null")


@without_fips
def test_openssl_hashes(auto_container):
    """If the host is not running in fips mode, then we check that all hash
    algorithms work (except for ``gost``, which has been disabled) via
    :command:`openssl $digest /dev/null`.

    """
    for md in ALL_DIGESTS:
        if md == "gost":
            continue
        auto_container.connection.run_expect([0], f"openssl {md} /dev/null")

    assert (
        auto_container.connection.run_expect(
            [1], "openssl gost /dev/null"
        ).stderr.strip()
        == "gost is not a known digest"
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
    assert len(hashes) == len(ALL_DIGESTS)
    assert set(hashes) == set(ALL_DIGESTS)


@pytest.mark.xfail(
    reason="Rancher cannot be build without a secret value anymore"
)
@pytest.mark.parametrize(
    "host_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/rancher/rancher",
        ).to_pytest_param()
    ],
    indirect=["host_git_clone"],
)
@pytest.mark.skipif(
    not DOCKER_SELECTED, reason="Dapper only works with docker"
)
def test_rancher_build(host, host_git_clone, dapper):
    """Regression test that we can build Rancher in the base container:

    - clone the `rancher/rancher <https://github.com/rancher/rancher>`_ repository
    - monkey patch their :file:`Dockerfile.dapper` replacing their container
      image with the url or id of the base container
    - monkey patch their :file:`Dockerfile.dapper` further removing their
      version pin of the docker version
    - run :command:`dapper build`

    This test is only enabled for docker (dapper does not support podman).
    """
    dest, git_repo = host_git_clone
    rancher_dir = dest / git_repo.repo_name
    with open(rancher_dir / "Dockerfile.dapper", "r") as dapperfile:
        contents = dapperfile.read(-1)

    with open(rancher_dir / "Dockerfile.dapper", "w") as dapperfile:
        dapperfile.write(
            re.sub(
                r"FROM .*",
                f"FROM {container_from_pytest_param(BASE_CONTAINER).container_id or container_from_pytest_param(BASE_CONTAINER).url}",
                contents,
            ),
        )

    # FIMXE: enable dapper ci at some point instead of just dapper build
    # host.run_expect([0], f"cd {rancher_dir} && {dapper} ci")
    host.run_expect([0], f"cd {rancher_dir} && {dapper} build")


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
