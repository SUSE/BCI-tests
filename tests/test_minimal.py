from typing import Dict

import pytest
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from pytest_container.runtime import LOCALHOST


CONTAINER_IMAGES = [MINIMAL_CONTAINER, MICRO_CONTAINER]

#: size limits of the minimal image per architecture in MiB
MINIMAL_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 40,
    "aarch64": 44,
    "s390x": 40,
    "ppc64le": 51,
}
#: size limits of the micro image per architecture in MiB
MICRO_IMAGE_MAX_SIZE: Dict[str, int] = {
    "x86_64": 25,
    "aarch64": 26,
    "s390x": 25,
    "ppc64le": 31,
}


@pytest.mark.parametrize(
    "container,size",
    [
        pytest.param(
            MINIMAL_CONTAINER,
            MINIMAL_IMAGE_MAX_SIZE,
            marks=pytest.mark.xfail(
                reason="Temporary size increase due to mozilla cert bundle hack"
            ),
        ),
        (MICRO_CONTAINER, MICRO_IMAGE_MAX_SIZE),
    ],
    indirect=["container"],
)
def test_minimal_image_size(
    container, size: Dict[str, int], container_runtime
):
    """Check that the size of the minimal container is below the limits specified in
    :py:const:`MINIMAL_IMAGE_MAX_SIZE` and that the size of the micro container
    is below the limits from :py:const:`MICRO_IMAGE_MAX_SIZE`.

    """
    assert (
        container_runtime.get_image_size(container.image_url_or_id)
        < size[LOCALHOST.system_info.arch] * 1024 * 1024
    )


def test_fat_packages_absent(auto_container):
    """Verify that the following binaries do not exist:
    - :command:`zypper`
    - :command:`grep`
    - :command:`diff`
    - :command:`sed`
    - :command:`info`
    - :command:`man`
    """
    for pkg in ("zypper", "grep", "diff", "sed", "info", "man"):
        assert not auto_container.connection.exists(pkg)


@pytest.mark.parametrize(
    "container", [MICRO_CONTAINER], indirect=["container"]
)
def test_rpm_absent_in_micro(container):
    """Ensure that rpm is not present in the micro container."""
    assert not container.connection.exists(
        "rpm"
    ), "rpm must not be present in the micro container"


@pytest.mark.parametrize(
    "container", [MINIMAL_CONTAINER], indirect=["container"]
)
def test_rpm_present_in_micro(container):
    """Ensure that rpm is present in the minimal container."""
    assert container.connection.exists(
        "rpm"
    ), "rpm must be present in the minimal container"
