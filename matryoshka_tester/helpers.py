from abc import ABC, abstractmethod
from dataclasses import dataclass
from os import getenv
from typing import Any, Optional
import pytest

import testinfra


@dataclass(frozen=True)
class ToParamMixin:
    """
    Mixin class that gives child classes the ability to convert themselves into
    a pytest.param with self.__str__() as the default id and optional marks
    """

    marks: Any = None

    def to_pytest_param(self):
        return pytest.param(self, id=self.__str__(), marks=self.marks or ())


@dataclass(frozen=True)
class OciRuntimeBase(ABC, ToParamMixin):
    #: command that builds the Dockerfile in the current working directory
    build_command: str = ""
    #: the "main" binary of this runtime, e.g. podman or docker
    runner_binary: str = ""
    _runtime_functional: bool = False

    def __post_init__(self) -> None:
        if not self.build_command or not self.runner_binary:
            raise ValueError(
                f"build_command ({self.build_command=}) or runner_binary "
                f"({self.runner_binary=}) were not specified"
            )
        if not self._runtime_functional:
            raise RuntimeError(
                f"The runtime {self.__class__.__name__} is not functional!"
            )

    @abstractmethod
    def get_image_id_from_stdout(self, stdout: str) -> str:
        pass

    def __str__(self) -> str:
        return self.__class__.__name__


LOCALHOST = testinfra.host.get_host("local://")


class PodmanRuntime(OciRuntimeBase):

    _runtime_functional = (
        LOCALHOST.run("podman ps").succeeded
        and LOCALHOST.run("buildah").succeeded
    )

    def __init__(self) -> None:
        super().__init__(
            build_command="buildah bud",
            runner_binary="podman",
            _runtime_functional=self._runtime_functional,
        )

    def get_image_id_from_stdout(self, stdout: str) -> str:
        # buildah prints the full image hash to the last non-empty line
        return list(
            filter(None, map(lambda l: l.strip(), stdout.split("\n")))
        )[-1]


class DockerRuntime(OciRuntimeBase):

    _runtime_functional = LOCALHOST.run("docker ps").succeeded

    def __init__(self) -> None:
        super().__init__(
            build_command="docker build .",
            runner_binary="docker",
            _runtime_functional=self._runtime_functional,
        )

    def get_image_id_from_stdout(self, stdout: str) -> str:
        # docker build prints this into the last non-empty line:
        # Successfully built 1e3c746e8069
        # -> grab the last line (see podman) & the last entry
        last_line = list(
            filter(None, map(lambda l: l.strip(), stdout.split("\n")))
        )[-1]
        return last_line.split()[-1]


def get_selected_runtime() -> OciRuntimeBase:
    """Returns the container runtime that the user selected.

    It defaults to podman and selects docker if podman & buildah are not
    present. If podman and docker are both present, then docker is returned if
    the environment variable `CONTAINER_RUNTIME` is set to `docker`.

    If neither docker nor podman are available, then a ValueError is raised.
    """
    podman_exists = LOCALHOST.exists("podman") and LOCALHOST.exists("buildah")
    docker_exists = LOCALHOST.exists("docker")

    if podman_exists ^ docker_exists:
        return PodmanRuntime() if podman_exists else DockerRuntime()
    elif podman_exists and docker_exists:
        return (
            DockerRuntime()
            if getenv("CONTAINER_RUNTIME") == "docker"
            else PodmanRuntime()
        )

    raise ValueError("No suitable container runtime is present on the host")


@dataclass(frozen=True)
class ContainerBuild(ToParamMixin):
    """Test information storage for running docker builds from a Dockerfile in
    the dockerfiles/ subfolder. This fixture is to be used in conjunction with
    the dockerfile_build fixture.

    Each build corresponds to a file with the filename from the `name` field,
    that is copied by the `dockerfile_build` into a temporary working directory
    as `Dockerfile`. Afterwards, the pre_build_steps are run.

    TODO: post_build_steps are not run at the moment.
    """

    name: str = None
    pre_build_steps: Optional[str] = None
    post_build_steps: Optional[str] = None

    def __str__(self) -> str:
        return self.name

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("A ContainerBuild must have a name")
