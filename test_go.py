import os.path

import pytest

from matryoshka_tester.helpers import GitRepositoryBuild


GOLANG_MAX_CONTAINER_SIZE_ON_DISK = 1181116006  # 1.1GB uncompressed


def test_go_size(host, container, container_runtime):
    assert (
        container_runtime.get_image_size(container.image)
        < GOLANG_MAX_CONTAINER_SIZE_ON_DISK
    )


def test_go_version(container):
    assert container.version in container.connection.check_output("go version")


@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/weaveworks/kured.git",
            build_command="make cmd/kured/kured",
        ).to_pytest_param()
    ],
    indirect=["container_git_clone"],
)
def test_kured(container, container_git_clone):
    cmd = container.connection.run(container_git_clone.test_command)
    assert cmd.rc == 0


@pytest.mark.parametrize(
    "host_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/mvarlese/fleet",
        ).to_pytest_param()
    ],
    indirect=["host_git_clone"],
)
def test_fleet(host, host_git_clone, dapper):
    dest, _ = host_git_clone
    host.run_expect(
        [0],
        f"cd {os.path.join(dest, 'fleet')} && {dapper} build && {dapper} ci",
    )
