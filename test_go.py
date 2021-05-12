import pytest

from matryoshka_tester.helpers import GitRepositoryBuild


def test_go_version(container):
    assert container.version in container.connection.check_output("go version")


@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/weaveworks/kured.git",
            build_command="make cmd/kured/kured",
        ).to_pytest_param()
    ],
    indirect=["container_git_clone"],
)
def test_kured(container, container_git_clone):
    cmd = container.connection.run(container_git_clone.test_command)
    print(cmd.stdout)
    assert cmd.rc == 0
