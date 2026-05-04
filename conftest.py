import logging
import os
import shlex
import time
from pathlib import Path
from subprocess import check_output
from typing import Iterator
from typing import Tuple

import pytest
from _pytest.fixtures import SubRequest
from pytest_container import GitRepositoryBuild
from pytest_container import OciRuntimeBase
from pytest_container import auto_container_parametrize
from pytest_container.container import ContainerData
from pytest_container.helpers import add_extra_run_and_build_args_options
from pytest_container.helpers import add_logging_level_options
from pytest_container.helpers import set_logging_level_from_cli_args


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
    `GitRepositoryBuild` as a tuple to the test function requesting this.
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

    if os.getenv("TESTINFRA_LOGGING"):
        # log all calls performed by testinfra, so that we have a papertrail of what
        # was executed.
        # As an additional catch, we must take into account pytest-xdist
        # (i.e. parallelization): if we are running in xdist mode, then we create a
        # separate logfile for each worker as we'd potentially write into the same
        # log.
        worker_id = os.environ.get("PYTEST_XDIST_WORKER")
        file_handler = logging.FileHandler(
            f"commands-{int(time.time())}{'-' + worker_id if worker_id else ''}.txt"
        )

        logger = logging.getLogger("testinfra")
        logger.setLevel("DEBUG")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
