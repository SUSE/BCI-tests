import os
import shlex
import tempfile
import urllib.request
from pathlib import Path
from subprocess import check_output
from typing import Iterator
from typing import Tuple

import pytest
from _pytest.fixtures import SubRequest
from pytest_container import GitRepositoryBuild
from pytest_container import OciRuntimeBase
from pytest_container import Version
from pytest_container import auto_container_parametrize
from pytest_container.container import ContainerData
from pytest_container.helpers import add_extra_run_and_build_args_options
from pytest_container.helpers import add_logging_level_options
from pytest_container.helpers import set_logging_level_from_cli_args

from bci_tester.util import get_host_go_version


@pytest.fixture(scope="function")
def container_git_clone(
    request: SubRequest, tmp_path, container_runtime: OciRuntimeBase
):
    """This fixture clones the `GitRepositoryBuild` passed as an indirect
    parameter to it into the currently selected container.

    It returns the GitRepositoryBuild to the requesting test function.
    """
    if isinstance(request.param, GitRepositoryBuild):
        git_repo_build = request.param
    elif (
        hasattr(request.param, "values")
        and len(request.param.values) == 1
        and isinstance(request.param.values[0], GitRepositoryBuild)
    ):
        git_repo_build = request.param.values[0]
    else:
        raise ValueError(
            f"got an invalid request parameter {type(request.param)}, "
            "expected GitRepositoryBuild or SubRequest with a GitRepositoryBuild"
        )

    container_fixture = None
    for fixture_name in (
        "container",
        "auto_container",
        "container_per_test",
        "auto_container_per_test",
    ):
        if fixture_name in request.fixturenames:
            container_fixture = request.getfixturevalue(fixture_name)

    assert isinstance(container_fixture, ContainerData)

    assert container_fixture is not None, (
        "No container fixture was passed to the test function, cannot execute `container_git_clone`"
    )

    check_output(shlex.split(git_repo_build.clone_command), cwd=tmp_path)

    ctr_path = (
        container_fixture.inspect.config.workingdir / git_repo_build.repo_name
    )

    check_output(
        [
            container_runtime.runner_binary,
            "cp",
            str(tmp_path / git_repo_build.repo_name),
            f"{container_fixture.container_id}:{ctr_path}",
        ]
    )
    # fix file permissions for the git copied git repo
    check_output(
        [
            container_runtime.runner_binary,
            "exec",
            container_fixture.container_id,
            "/bin/sh",
            "-c",
            f"chown --recursive $(id -u):$(id -g) {git_repo_build.repo_name}",
        ]
    )
    yield git_repo_build


@pytest.fixture(scope="function")
def host_git_clone(
    request, host, tmp_path: Path
) -> Iterator[Tuple[Path, GitRepositoryBuild]]:
    """This fixture clones the `GitRepositoryBuild` into a temporary directory
    on the host system, `cd`'s into it and returns the path and the
    `GitRepositoryBuild` as a tuple to the test function requesting this it.
    """

    if isinstance(request.param, GitRepositoryBuild):
        git_repo_build = request.param
    elif (
        hasattr(request.param, "values")
        and len(request.param.values) == 1
        and isinstance(request.param.values[0], GitRepositoryBuild)
    ):
        git_repo_build = request.param.values[0]
    else:
        raise ValueError(
            f"got an invalid request parameter {type(request.param)}, "
            "expected GitRepositoryBuild or SubRequest with a GitRepositoryBuild"
        )
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        host.run_expect([0], git_repo_build.clone_command)
        yield tmp_path, git_repo_build
    finally:
        os.chdir(cwd)


def pytest_generate_tests(metafunc):
    auto_container_parametrize(metafunc)


def pytest_addoption(parser):
    add_extra_run_and_build_args_options(parser)
    add_logging_level_options(parser)


def pytest_configure(config):
    set_logging_level_from_cli_args(config)


@pytest.fixture(scope="module")
def dapper(host):
    """Fixture that ensures that dapper is installed on the host system and
    yields the path to the dapper binary.

    If dapper is already installed on the host, then its location is
    returned. Otherwise, dapper is either build from source inside a temporary
    directory or downloaded from rancher.com (if no go toolchain can be found).

    """
    # dapper has been installed => use that one
    if host.exists("dapper"):
        yield host.find_command("dapper")
        return

    def download_dapper(temporary_directory) -> str:
        with urllib.request.urlopen(
            "https://releases.rancher.com/dapper/latest/dapper-Linux-"
            + host.system_info.arch
        ) as f:
            dapper_path = os.path.join(temporary_directory, "dapper")
            with open(dapper_path, "wb") as dapper_file:
                dapper_file.write(f.read())
            os.chmod(dapper_path, 0o755)
            return dapper_path

    # go is not available on the host => fetch
    if not host.exists("go"):
        with tempfile.TemporaryDirectory() as tempdir:
            yield download_dapper(tempdir)
            return

    # build dapper from source if we have go
    with tempfile.TemporaryDirectory() as tmpdir:
        gopath = os.path.join(tmpdir, "gopath")

        # dapper needs go 1.17+ to build => fallback to downloading
        if get_host_go_version(host) < Version(1, 17):
            with tempfile.TemporaryDirectory() as tempdir:
                yield download_dapper(tempdir)
                return

        host.run_expect(
            [0],
            f"GOPATH={gopath} go install github.com/rancher/dapper@latest",
        )
        yield os.path.join(gopath, "bin", "dapper")

        # fix file permissions so that we can unlink them all
        for root, dirs, files in os.walk(gopath):
            for filename in files + dirs:
                full_path = os.path.join(root, filename)
                if not os.access(full_path, os.W_OK):
                    os.chmod(full_path, 0o755)
