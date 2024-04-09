"""Tests for Spack application build container images."""
# from pytest_container.build import MultiStageBuild
from textwrap import dedent

import pytest
from _pytest.config import Config
from pytest_container import MultiStageBuild
from pytest_container.container import BindMount
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.container import DerivedContainer
from pytest_container.helpers import get_extra_build_args
from pytest_container.helpers import get_extra_run_args

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import SPACK_CONTAINERS
from bci_tester.runtime_choice import PODMAN_SELECTED

# from pytest_container.container import Container

CONTAINER_IMAGES = SPACK_CONTAINERS


@pytest.mark.parametrize(
    "container",
    CONTAINER_IMAGES,
    indirect=True,
)
def test_spack(
    container,
    host,
    container_runtime,
    tmp_path,
    pytestconfig: Config,
):
    """Check if Spack Container allows to build an application container"""

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
                        final: "{DerivedContainer.get_base(container_and_marks_from_pytest_param(BASE_CONTAINER)[0]).url}"
        """
            )
        )
    # mount spack.yaml into container (/root)
    mount = BindMount(
        host_path=tmp_path / "spack.yaml",
        container_path="/root/spack.yaml",
    )

    # run container with argument: 'containerize', save output to variable 'containerfile'
    # Cannot use container.connection.run_expect(..,"containerize"):
    # This uses `podman exec` which does not allow to test the `oneshot`
    # feature of ENTRYPOINT: `podman run -v... --rm <container> containerize`
    # containerfile = container.connection.run_expect(
    #    [0],
    #    "containerize"
    # )
    containerfile = host.check_output(
        f"{container_runtime.runner_binary} run --rm {mount.cli_arg} "
        f"{' '.join(get_extra_run_args(pytestconfig))} "
        f"{container.image_url_or_id} containerize",
    )

    container.container.volume_mounts += [mount]
    multi_stage_build = MultiStageBuild(
        containers={
            "builder": container.container,
            "runner": BASE_CONTAINER,
        },
        containerfile_template=containerfile.replace("$", "$$"),
    )
    runner_id = multi_stage_build.build(
        tmp_path,
        pytestconfig,
        container_runtime,
        extra_build_args=get_extra_build_args(pytestconfig),
    )
    # Run resulting container and test whether zsh is running
    assert host.check_output(
        f"{container_runtime.runner_binary} run --rm "
        f"{' '.join(get_extra_build_args(pytestconfig))} "
        f"{runner_id} zsh -c 'echo $ZSH_VERSION' ",
    )
