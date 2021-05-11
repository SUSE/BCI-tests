import pytest
import testinfra
import subprocess
import os
import functools

from collections import namedtuple
from tempfile import TemporaryDirectory
from shutil import copy

from matryoshka_tester.parse_data import containers, CONTAINER_REGISTRY
from matryoshka_tester.helpers import get_selected_runtime, ContainerBuild

ContainerData = namedtuple("Container", ["version", "image", "connection"])


@pytest.fixture(scope="function")
def dockerfile_build(request, host):
    """Fixture that creates a temporary directory, copies the appropriate
    Dockerfile into it and runs the pre_build_steps from the ContainerBuild
    instance that must be passed as the request parameter to this fixture.
    """
    assert isinstance(
        request.param, ContainerBuild
    ), f"got an invalid request parameter {type(request.param)}"
    cwd = os.getcwd()
    try:
        with TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            copy(
                os.path.join(cwd, "dockerfiles", request.param.name),
                os.path.join(tmp_dir, "Dockerfile"),
            )
            if request.param.pre_build_steps:
                host.run_expect([0], request.param.pre_build_steps)

            yield tmp_dir

    finally:
        os.chdir(cwd)


@pytest.fixture(scope="module")
def container_runtime():
    return get_selected_runtime()


@pytest.fixture(scope="module")
def container(request, container_runtime):
    container_id = (
        subprocess.check_output(
            [
                container_runtime.runner_binary,
                "run",
                "-d",
                "-it",
                request.param[1],
                "/bin/sh",
            ]
        )
        .decode()
        .strip()
    )
    yield ContainerData(
        *request.param,
        testinfra.get_host(
            f"{container_runtime.runner_binary}://{container_id}"
        ),
    )
    subprocess.check_call(
        [container_runtime.runner_binary, "rm", "-f", container_id]
    )


def pytest_generate_tests(metafunc):
    # Finds container_type.
    # If necessary, you can override the detection by setting a variable "container_type" in your module.
    container_type = getattr(metafunc.module, "container_type", "")
    if container_type == "":
        container_type = (
            os.path.basename(metafunc.module.__file__)
            .strip()
            .replace("test_", "")
            .replace(".py", "")
        )

    if "container" in metafunc.fixturenames:
        metafunc.parametrize(
            "container",
            [
                (
                    container.version,
                    "/".join(
                        [CONTAINER_REGISTRY, container.repo, container.image]
                    )
                    + ":"
                    + container.tag,
                )
                for container in containers
                if container.type == container_type
            ],
            ids=[
                container.version
                for container in containers
                if container.type == container_type
            ],
            indirect=True,
        )


def restrict_to_version(versions):
    def inner(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                c = kwargs.get("container")
            except KeyError:
                print("Unexpected structure, did you use container fixture?")
            else:
                if c.version in versions:
                    return func(*args, **kwargs)
                else:
                    return pytest.skip(
                        "Version restrict used and current version doesn't match"
                    )

        return wrapper

    return inner
