import os
import shlex
import tempfile
from subprocess import check_output

import pytest
from pytest_container import auto_container_parametrize
from pytest_container import get_selected_runtime
from pytest_container import GitRepositoryBuild


@pytest.fixture(scope="function")
def container_git_clone(request, tmp_path):
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

    check_output(shlex.split(git_repo_build.clone_command), cwd=tmp_path)

    if "container" in request.fixturenames:
        cont = request.getfixturevalue("container")
    else:
        cont = request.getfixturevalue("auto_container")
    runtime = get_selected_runtime()
    check_output(
        [
            runtime.runner_binary,
            "cp",
            str(tmp_path / git_repo_build.repo_name),
            f"{cont.container_id}:/{git_repo_build.repo_name}",
        ]
    )
    yield git_repo_build


@pytest.fixture(scope="function")
def host_git_clone(request, host, tmp_path):
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


@pytest.fixture(scope="module")
def dapper(host):
    """Fixture that ensures that dapper is installed on the host system and
    yields the path to the dapper binary.

    If dapper is already installed on the host, then its location is
    returned. Otherwise, dapper is either build from source inside a temporary
    directory or downloaded from rancher.com (if no go toolchain can be found).

    """
    if host.exists("dapper"):
        yield host.find_command("dapper")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        gopath = os.path.join(tmpdir, "gopath")
        host.run_expect(
            [0], f"GOPATH={gopath} go get github.com/rancher/dapper"
        )
        yield os.path.join(gopath, "bin", "dapper")
