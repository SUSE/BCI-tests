"""Tests for Spack application build container images."""

from textwrap import dedent

import pytest
from _pytest.config import Config
from pytest_container import MultiStageBuild
from pytest_container.container import BindMount
from pytest_container.container import DerivedContainer
from pytest_container.container import ImageFormat
from pytest_container.helpers import get_extra_build_args
from pytest_container.helpers import get_extra_run_args

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import SPACK_CONTAINERS
from bci_tester.runtime_choice import PODMAN_SELECTED


@pytest.mark.parametrize(
    "container",
    SPACK_CONTAINERS,
    indirect=True,
)
def test_spack(
    container,
    host,
    container_runtime,
    tmp_path,
    pytestconfig: Config,
) -> None:
    """
    Test if Spack Container can build a zsh container.

    This function creates a `spack.yaml` input for spack, mounts it into the container,
    runs the container with the 'containerize' argument which provides a `Containerfile`
    multi-stage build description to build a zsh container.

    For the final stage, the base container of the spack container is being used.

    The test is building this description as a multi-stage container,
    and finally tests whether the zsh in the resulting container can be
    successfully launched.
    """
    # Create spack.yaml file in temporary directory
    with open(tmp_path / "spack.yaml", "w", encoding="utf-8") as spack_yaml:
        spack_yaml.write(
            dedent(
                f"""
            spack:
                specs:
                    - zsh

                container:
                    format: docker
                    images:
                        build: "{container.image_url_or_id}"
                        final: "{DerivedContainer.get_base(BASE_CONTAINER).url}"
        """
            )
        )
    # mount spack.yaml into container (/root)
    mount_arg = BindMount(
        host_path=tmp_path / "spack.yaml",
        container_path="/root/spack.yaml",
    ).cli_arg

    # run container with argument: 'containerize', save output to variable 'containerfile'
    containerfile = host.check_output(
        f"{container_runtime.runner_binary} run --rm {mount_arg} "
        f"{' '.join(get_extra_run_args(pytestconfig))} "
        f"{container.image_url_or_id} containerize",
    )

    multi_stage_build = MultiStageBuild(
        containers={
            "builder": container.container,
            "runner": BASE_CONTAINER,
        },
        containerfile_template=containerfile.replace("$", "$$"),
    )

    build_args = get_extra_run_args(pytestconfig)
    if PODMAN_SELECTED:
        build_args += ["--format", str(ImageFormat.DOCKER)]

    runner_id = multi_stage_build.build(
        tmp_path, pytestconfig, container_runtime, extra_build_args=build_args
    )
    # Run resulting container and test whether zsh is running
    assert host.check_output(
        f"{container_runtime.runner_binary} run --rm "
        f"{' '.join(get_extra_build_args(pytestconfig))} "
        f"{runner_id} zsh -c 'echo $ZSH_VERSION' ",
    )
