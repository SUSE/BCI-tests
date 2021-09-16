import pytest
from bci_tester.data import NODEJS_12_CONTAINER
from bci_tester.data import NODEJS_14_CONTAINER
from bci_tester.helpers import GitRepositoryBuild


CONTAINER_IMAGES = [NODEJS_12_CONTAINER, NODEJS_14_CONTAINER]


def test_node_version(auto_container):
    assert (
        auto_container.connection.run_expect([0], "node -v")
        .stdout.strip()
        .replace("v", "")
        .split(".")[0]
        == auto_container.connection.run_expect(
            [0], "echo $NODE_VERSION"
        ).stdout.strip()
    )


def test_npm_version(auto_container):
    npm_version = auto_container.connection.run_expect(
        [0], "npm --version"
    ).stdout.strip()
    npm_version_from_env = auto_container.connection.run_expect(
        [0], "echo $NPM_VERSION"
    ).stdout.strip()

    assert npm_version == npm_version_from_env


@pytest.mark.parametrize(
    "container_git_clone",
    [
        pkg.to_pytest_param()
        for pkg in (
            GitRepositoryBuild(
                repository_url="https://github.com/lodash/lodash.git",
                build_command="npm ci && npm test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/chalk/chalk.git",
                build_command="npm install && npm test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/tj/commander.js.git",
                build_command="npm ci && npm test && npm run lint",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/expressjs/express.git",
                build_command="""npm config set shrinkwrap false &&
                    npm rm --silent --save-dev connect-redis &&
                    npm run test-ci &&
                    npm run lint
                    """,
            ),
            GitRepositoryBuild(
                build_command="""npm install -g grunt-cli &&
                    npm install &&
                    grunt test
                    """,
                repository_url="https://github.com/moment/moment",
            ),
            GitRepositoryBuild(
                build_command="""npm -g install yarn &&
                    yarn --frozen-lockfile &&
                    yarn run build &&
                    yarn run pretest &&
                    yarn run tests-only
                    """,
                repository_url="https://github.com/facebook/prop-types",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/jprichardson/node-fs-extra",
                build_command="npm install && npm run unit",
            ),
        )
    ],
    indirect=["container_git_clone"],
)
def test_popular_npm_repos(auto_container, container_git_clone):
    cmd = auto_container.connection.run(container_git_clone.test_command)
    assert cmd.rc == 0
