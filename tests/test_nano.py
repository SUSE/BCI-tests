"""This module contains the tests for the nano container, the image with only CA and timezone pre-installed."""

import pytest
from _pytest.config import Config
from pytest_container import MultiStageBuild
from pytest_container import get_extra_build_args
from pytest_container import get_extra_run_args
from pytest_container.container import ImageFormat

from bci_tester.data import NANO_CONTAINER
from bci_tester.runtime_choice import PODMAN_SELECTED

CONTAINER_IMAGES = (NANO_CONTAINER,)


MULTISTAGE_DOCKERFILE = """FROM $builder as builder
WORKDIR /src
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build main.go

FROM $runner
ENTRYPOINT []
WORKDIR /fetcher/
COPY --from=builder /src/main .
CMD ["/fetcher/main"]
"""


@pytest.mark.parametrize(
    "container",
    CONTAINER_IMAGES,
    indirect=True,
)
def test_nano_certificates(
    container, host, tmp_path, container_runtime, pytestconfig: Config
):
    """This is a multistage container build, verifying that the certificates are
    correctly set up in the containers.

    In the first step, we build a go binary from
    :py:const:`FETCH_SUSE_DOT_COM` in the golang container. We copy the
    resulting binary into the container under test and execute it in that
    container.

    If the certificates are incorrectly set up, then the GET request will fail.
    """
    multi_stage_build = MultiStageBuild(
        containers={
            "builder": "registry.suse.com/bci/golang:latest",
            "runner": NANO_CONTAINER,
        },
        containerfile_template=MULTISTAGE_DOCKERFILE,
    )
    multi_stage_build.prepare_build(
        tmp_path, container_runtime, pytestconfig.rootpath
    )

    with open(tmp_path / "main.go", "w", encoding="utf-8") as main_go:
        main_go.write("""package main

import "net/http"

func main() {
        _, err := http.Get("https://updates.suse.com/-/healthy")
        if err != nil {
                panic(err)
        }
}
""")

    build_args = get_extra_run_args(pytestconfig)
    if PODMAN_SELECTED:
        build_args += ["--format", str(ImageFormat.DOCKER)]

    runner_id = multi_stage_build.build(
        tmp_path, pytestconfig, container_runtime, extra_build_args=build_args
    )
    # Run resulting container and test whether zsh is running
    assert (
        host.check_output(
            f"{container_runtime.runner_binary} run --rm "
            f"{' '.join(get_extra_build_args(pytestconfig))} "
            f"{runner_id} ",
        ).strip()
        == ""
    )
