"""Tests for the Go language container."""
import pytest
from bci_tester.data import GO_1_16_BASE_CONTAINER
from bci_tester.data import GO_1_16_CONTAINER
from pytest_container import GitRepositoryBuild


#: Maximum go container size in Bytes
GOLANG_MAX_CONTAINER_SIZE_ON_DISK = 1181116006  # 1.1GB uncompressed

CONTAINER_IMAGES = [GO_1_16_BASE_CONTAINER, GO_1_16_CONTAINER]


@pytest.mark.parametrize(
    "container", [GO_1_16_BASE_CONTAINER], indirect=["container"]
)
def test_go_size(container, container_runtime):
    """Ensure that the go base container is below the size specified in
    :py:const:`GOLANG_MAX_CONTAINER_SIZE_ON_DISK`.

    """
    assert (
        container_runtime.get_image_size(container.image_url_or_id)
        < GOLANG_MAX_CONTAINER_SIZE_ON_DISK
    )


def test_go_version(auto_container):
    """Check that the environment variable ``GOLANG_VERSION`` matches the output of
    :command:`go version`

    """
    assert auto_container.connection.check_output(
        "echo $GOLANG_VERSION"
    ) in auto_container.connection.check_output("go version")


@pytest.mark.parametrize(
    "container_per_test,container_git_clone",
    [
        (
            GO_1_16_CONTAINER,
            GitRepositoryBuild(
                repository_url="https://github.com/weaveworks/kured.git",
                build_command="make cmd/kured/kured",
            ).to_pytest_param(),
        ),
    ],
    indirect=["container_per_test", "container_git_clone"],
)
def test_build_kured(container_per_test, container_git_clone):
    """Try to build `kured <https://github.com/weaveworks/kured.git>`_ inside the
    container with :command:`make` pre-installed.

    """
    container_per_test.connection.run_expect(
        [0], container_git_clone.test_command
    )
