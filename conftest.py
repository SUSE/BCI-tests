import asyncio
import functools
import os
import shlex
import tempfile
from typing import Any
from typing import NamedTuple
from typing import Optional
from typing import Union

import pytest
import testinfra
from bci_tester.data import Container
from bci_tester.data import DerivedContainer
from bci_tester.helpers import check_output
from bci_tester.helpers import get_selected_runtime
from bci_tester.helpers import GitRepositoryBuild
from requests import get


class ContainerData(NamedTuple):
    image_url: str
    container_id: str
    connection: Any


@pytest.fixture(scope="function")
async def container_git_clone(request, tmp_path):
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

    await check_output(shlex.split(git_repo_build.clone_command), cwd=tmp_path)

    if "container" in request.fixturenames:
        cont = request.getfixturevalue("container")
    else:
        cont = request.getfixturevalue("auto_container")
    runtime = get_selected_runtime()
    await check_output(
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


@pytest.fixture(scope="module")
def container_runtime():
    return get_selected_runtime()


@pytest.fixture(scope="module")
def event_loop():
    return asyncio.get_event_loop()


@pytest.fixture(scope="module")
async def auto_container(request, container_runtime):
    """Fixture that will build & launch a container that is either passed as a
    request parameter or it will be automatically parametrized via
    pytest_generate_tests.
    """
    launch_data: Union[Container, DerivedContainer] = request.param

    container_id: Optional[str] = None
    try:
        await launch_data.prepare_container()
        container_id = await check_output(
            [container_runtime.runner_binary] + launch_data.launch_cmd
        )
        yield ContainerData(
            image_url=launch_data.url,
            container_id=container_id,
            connection=testinfra.get_host(
                f"{container_runtime.runner_binary}://{container_id}"
            ),
        )
    except RuntimeError as exc:
        raise exc
    finally:
        if container_id is not None:
            await check_output(
                [container_runtime.runner_binary, "rm", "-f", container_id]
            )


container = auto_container


def pytest_generate_tests(metafunc):
    container_images = getattr(metafunc.module, "CONTAINER_IMAGES", None)
    if (
        "auto_container" in metafunc.fixturenames
        and container_images is not None
    ):
        metafunc.parametrize("auto_container", container_images, indirect=True)


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
        if host.exists("go"):
            gopath = os.path.join(tmpdir, "gopath")
            host.run_expect(
                [0], f"GOPATH={gopath} go get github.com/rancher/dapper"
            )
            yield os.path.join(gopath, "bin", "dapper")
        else:
            resp = get(
                "https://releases.rancher.com/dapper/latest/dapper-"
                + host.system_info.type.capitalize()
                + "-"
                + host.system_info.arch
            )
            dest = os.path.join(tmpdir, "dapper")
            with open(dest, "wb") as dapper_file:
                dapper_file.write(resp.content)
            yield dest


def restrict_to_containers(containers):
    def inner(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            c = kwargs.get("auto_container")
            try:
                len(containers)
            except TypeError:
                urls = [containers.url]
            else:
                urls = [cont.url for cont in containers]

            # raise Exception(c.image_url, urls)
            if c is not None and c.image_url in urls:
                return func(*args, **kwargs)

            return pytest.skip(
                "Test is being restricted to the containers " + ", ".join(urls)
            )

        return wrapper

    return inner
