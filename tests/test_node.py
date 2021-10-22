import pytest
from bci_tester.data import NODEJS_12_CONTAINER
from bci_tester.data import NODEJS_14_CONTAINER
from pytest_container import GitRepositoryBuild


CONTAINER_IMAGES = [NODEJS_12_CONTAINER, NODEJS_14_CONTAINER]


def test_node_version(auto_container):
    """Verify that the environment variable ``NODE_VERSION`` matches the major
    version of the installed :command:`node` binary.

    """
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
    """Check that the environment variable ``NPM_VERSION`` matches the output of
    :command:`npm --version`.

    """
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
def test_popular_npm_repos(auto_container_per_test, container_git_clone):
    """Try to build and run the tests of a few popular npm packages:

    .. list-table::
       :header-rows: 1

       * - package
         - build command
       * - `Lodash <https://github.com/lodash/lodash.git>`_
         - :command:`npm ci && npm test`
       * - `chalk <https://github.com/chalk/chalk.git>`_
         - :command:`npm install && npm test`
       * - `Commander.js <https://github.com/tj/commander.js.git>`_
         - :command:`npm ci && npm test && npm run lint`
       * - `Express <https://github.com/expressjs/express.git>`_
         - :command:`npm config set shrinkwrap false && npm rm --silent --save-dev connect-redis && npm run test-ci && npm run lint`
       * - `moment <https://github.com/moment/moment>`_
         - :command:`npm install -g grunt-cli && npm install && grunt test`
       * - `prop-types <https://github.com/facebook/prop-types>`_
         - :command:`npm -g install yarn && yarn --frozen-lockfile && yarn run build && yarn run pretest && yarn run tests-only`
       * - `node-fs-extra <https://github.com/jprichardson/node-fs-extra>`_
         - :command:`npm install && npm run unit`

    """
    auto_container_per_test.connection.run_expect(
        [0], container_git_clone.test_command
    )
