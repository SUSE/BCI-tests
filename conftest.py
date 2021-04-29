import pytest
import testinfra
import subprocess
import os
import functools

from collections import namedtuple
from matryoshka_tester.data import containers

ContainerData = namedtuple("Container", ["version", "image", "connection"])


@pytest.fixture(scope="module")
def container(request):
    docker_id = (
        subprocess.check_output(
            ["docker", "run", "-d", "-it", request.param[1], "/bin/sh"]
        )
        .decode()
        .strip()
    )
    yield ContainerData(*request.param, testinfra.get_host("docker://" + docker_id))
    subprocess.check_call(["docker", "rm", "-f", docker_id])


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
                (ver, containers[container_type][ver])
                for ver in containers[container_type]
            ],
            ids=[ver for ver in containers[container_type]],
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
