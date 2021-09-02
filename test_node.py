from bci_tester.data import NODE_CONTAINER
import pytest

from bci_tester.helpers import GitRepositoryBuild


CONTAINER_IMAGE = NODE_CONTAINER


def test_node_version(auto_container):
    assert (
        auto_container.connection.run_expect([0], "node -v")
        .stdout.strip()
        .replace("v", "")
        .split(".")[0]
        == "14"
    )


def test_npm_and_yarn(auto_container):
    assert auto_container.connection.run_expect([0], "npm version")
    assert auto_container.connection.run_expect([0], "yarn --version")


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
                repository_url="https://github.com/visionmedia/debug.git",
                build_command="""
                    npm install &&
                    npm run lint &&
                    npm run test:node
                    """,
                marks=pytest.mark.xfail(
                    reason="Unexpected use of file extension 'js' for './browser.js' when building src/index.js"
                ),
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
                build_command="""yarn install &&
                    npm install --no-save "react@~16" "react-dom@~16" &&
                    yarn run pretest &&
                    yarn run tests-only &&
                    yarn run build
                    """,
                repository_url="https://github.com/facebook/prop-types",
                marks=pytest.mark.skip(reason="Broken for some reason"),
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
