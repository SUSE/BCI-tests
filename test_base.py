import re
from typing import Dict

import pytest
from bci_tester.data import BASE_CONTAINER
from bci_tester.fips import ALL_DIGESTS
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import NONFIPS_DIGESTS
from pytest_container import get_selected_runtime
from pytest_container import GitRepositoryBuild
from pytest_container.runtime import LOCALHOST

#: size limits of the base container per arch
BASE_CONTAINER_MAX_SIZE: Dict[str, int] = {
    "x86_64": 120,
    "aarch64": 130,
    "ppc64le": 150,
    "s390x": 120,
}

CONTAINER_IMAGES = [BASE_CONTAINER]


# Generic tests
def test_passwd_present(auto_container):
    assert auto_container.connection.file("/etc/passwd").exists


def test_base_size(auto_container, container_runtime):
    assert (
        container_runtime.get_image_size(auto_container.image_url_or_id)
        < BASE_CONTAINER_MAX_SIZE[LOCALHOST.system_info.arch] * 1024 * 1024
    )


# FIPS tests
with_fips = pytest.mark.skipif(
    not host_fips_enabled(), reason="host not running in FIPS 140 mode"
)
without_fips = pytest.mark.skipif(
    host_fips_enabled(), reason="host running in FIPS 140 mode"
)


@with_fips
def test_openssl_fips_hashes(auto_container):
    for md in NONFIPS_DIGESTS:
        cmd = auto_container.connection.run(f"openssl {md} /dev/null")
        assert cmd.rc != 0
        assert "not a known digest" in cmd.stderr

    for md in FIPS_DIGESTS:
        auto_container.connection.run_expect([0], f"openssl {md} /dev/null")


@without_fips
def test_openssl_hashes(auto_container):
    for md in ALL_DIGESTS:
        if md == "gost":
            continue
        auto_container.connection.run_expect([0], f"openssl {md} /dev/null")

    assert (
        auto_container.connection.run_expect(
            [1], f"openssl gost /dev/null"
        ).stderr.strip()
        == "gost is not a known digest"
    )


@pytest.mark.parametrize(
    "host_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/rancher/rancher",
            marks=pytest.mark.xfail(reason="dapper ci is broken"),
        ).to_pytest_param()
    ],
    indirect=["host_git_clone"],
)
@pytest.mark.skipif(
    get_selected_runtime().runner_binary != "docker",
    reason="Dapper only works with docker",
)
def test_rancher_build(host, host_git_clone, dapper):
    dest, git_repo = host_git_clone
    rancher_dir = dest / git_repo.repo_name
    with open(rancher_dir / "Dockerfile.dapper", "r") as dapperfile:
        contents = dapperfile.read(-1)

    with open(rancher_dir / "Dockerfile.dapper", "w") as dapperfile:
        dapperfile.write(
            re.sub(
                r"FROM .*",
                f"FROM {BASE_CONTAINER.container_id or BASE_CONTAINER.url}",
                contents,
            )
        )

    host.run_expect([0], f"cd {rancher_dir} && {dapper} ci")
