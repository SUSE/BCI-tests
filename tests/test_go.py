"""Tests for the Go language container."""
import pytest
from pytest_container import GitRepositoryBuild

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import GO_1_16_CONTAINER
from bci_tester.data import GO_1_17_CONTAINER
from bci_tester.data import GO_1_18_CONTAINER


#: Maximum go container size in Bytes
GOLANG_MAX_CONTAINER_SIZE_ON_DISK = 1181116006  # 1.1GB uncompressed

CONTAINER_IMAGES = [GO_1_16_CONTAINER, GO_1_17_CONTAINER, GO_1_18_CONTAINER]


def test_go_size(auto_container, container_runtime):
    """Ensure that the go base container is below the size specified in
    :py:const:`GOLANG_MAX_CONTAINER_SIZE_ON_DISK`.

    """
    assert (
        container_runtime.get_image_size(auto_container.image_url_or_id)
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
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/weaveworks/kured.git",
            repository_tag="1.9.2",
            build_command="make cmd/kured/kured",
        ).to_pytest_param(),
    ],
    indirect=["container_git_clone"],
)
def test_build_kured(auto_container_per_test, container_git_clone):
    """Try to build `kured <https://github.com/weaveworks/kured.git>`_ inside the
    container with :command:`make` pre-installed.

    """
    auto_container_per_test.connection.run_expect(
        [0], container_git_clone.test_command
    )


def test_go_get_binary_in_path(auto_container_per_test):
    """Check that binaries installed via ``go install`` can be invoked (i.e. are in
    the ``$PATH``).

    """
    auto_container_per_test.connection.run_expect(
        [0], "go install github.com/tylertreat/comcast@latest"
    )
    assert (
        "Comcast"
        in auto_container_per_test.connection.run_expect(
            [0], "comcast -version"
        ).stdout
    )


@pytest.mark.parametrize("container", [BASE_CONTAINER], indirect=True)
def test_base_PATH_present(auto_container, container):
    """Regression test that we did not accidentally omit parts of ``$PATH`` that are
    present in he base container in the golang containers.

    """
    path_in_go_container = auto_container.connection.run_expect(
        [0], "echo $PATH"
    ).stdout.strip()
    path_in_base_container = container.connection.run_expect(
        [0], "echo $PATH"
    ).stdout.strip()
    assert path_in_base_container in path_in_go_container
