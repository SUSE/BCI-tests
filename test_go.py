import pytest
from bci_tester.data import GO_1_16_BASE_CONTAINER
from bci_tester.data import GO_1_16_CONTAINER
from pytest_container import GitRepositoryBuild


GOLANG_MAX_CONTAINER_SIZE_ON_DISK = 1181116006  # 1.1GB uncompressed

CONTAINER_IMAGES = [GO_1_16_BASE_CONTAINER, GO_1_16_CONTAINER]


@pytest.mark.parametrize(
    "container", [GO_1_16_BASE_CONTAINER], indirect=["container"]
)
def test_go_size(container, container_runtime):
    assert (
        container_runtime.get_image_size(container.image_url_or_id)
        < GOLANG_MAX_CONTAINER_SIZE_ON_DISK
    )


def test_go_version(auto_container):
    assert auto_container.connection.check_output(
        "echo $GOLANG_VERSION"
    ) in auto_container.connection.check_output("go version")


@pytest.mark.parametrize(
    "container,container_git_clone",
    [
        (
            GO_1_16_CONTAINER,
            GitRepositoryBuild(
                repository_url="https://github.com/weaveworks/kured.git",
                build_command="make cmd/kured/kured",
            ).to_pytest_param(),
        ),
    ],
    indirect=["container", "container_git_clone"],
)
def test_kured(container, container_git_clone):
    container.connection.run_expect([0], container_git_clone.test_command)
