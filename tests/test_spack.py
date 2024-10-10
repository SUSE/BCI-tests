"""Tests for Spack application build container images."""

import pytest
from _pytest.config import Config
from pytest_container.container import ContainerImageData
from pytest_container.container import ContainerLauncher
from pytest_container.container import DerivedContainer
from pytest_container.container import EntrypointSelection
from pytest_container.container import ImageFormat
from pytest_container.container import MultiStageContainer
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import SPACK_CONTAINERS

BASE_CTR, _ = container_and_marks_from_pytest_param(BASE_CONTAINER)
assert isinstance(BASE_CTR, DerivedContainer)

SPACK_IMAGES_WITH_YAML_CONFIG = []

for param in SPACK_CONTAINERS:
    spac_ctr, spac_marks = container_and_marks_from_pytest_param(param)
    assert isinstance(spac_ctr, DerivedContainer)

    SPACK_IMAGES_WITH_YAML_CONFIG.append(
        pytest.param(
            DerivedContainer(
                base=spac_ctr,
                containerfile=rf"""SHELL ["/bin/bash", "-c"]
RUN echo $'spack: \n\
    specs: \n\
        - zsh \n\
    container: \n\
        format: docker \n\
        images: \n\
            build: "{spac_ctr.baseurl}" \n\
            final: "{BASE_CTR.baseurl}" \n\
' > /root/spack.yaml
""",
            ),
            marks=spac_marks or [],
            id=param.id,
        )
    )


@pytest.mark.parametrize(
    "container_image", SPACK_IMAGES_WITH_YAML_CONFIG, indirect=True
)
def test_spack(
    container_image: ContainerImageData,
    host,
    container_runtime: OciRuntimeBase,
    pytestconfig: Config,
) -> None:
    """Test if Spack Container can build a zsh container.

    This function uses the spack container image with a :file:`spack.yaml`
    embedded in the image to run :command:`spack containerize` which outputs a
    `Containerfile` multi-stage build description to build a zsh container.

    The test is building this description as a multi-stage container,
    and finally tests whether the zsh in the resulting container can be
    successfully launched.

    """
    containerfile = host.check_output(
        f"{container_image.run_command} containerize"
    )

    ctr = MultiStageContainer(
        containerfile=containerfile.replace("$", "$$"),
        image_format=ImageFormat.DOCKER,
        entry_point=EntrypointSelection.IMAGE,
    )

    with ContainerLauncher.from_pytestconfig(
        container=ctr,
        container_runtime=container_runtime,
        pytestconfig=pytestconfig,
    ) as launcher:
        launcher.prepare_container()
        ci = launcher.container_image_data

        host.check_output(f"{ci.run_command} zsh -c 'echo $ZSH_VERSION'")
