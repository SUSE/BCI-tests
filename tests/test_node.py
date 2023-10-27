"""Tests for the Node.js base container images."""
from textwrap import dedent

import pytest
from pytest_container import GitRepositoryBuild
from pytest_container.container import ContainerData

from bci_tester.data import NODEJS_CONTAINERS

CONTAINER_IMAGES = NODEJS_CONTAINERS


def test_node_version(auto_container):
    """Verify that the environment variable ``NODE_VERSION`` matches the major
    version of the installed :command:`node` binary.

    """
    assert auto_container.connection.check_output("node -v").replace(
        "v", ""
    ).split(".")[0] == auto_container.connection.check_output(
        "echo $NODE_VERSION"
    )


@pytest.mark.parametrize(
    "container_git_clone",
    [
        pkg.to_pytest_param()
        for pkg in (
            GitRepositoryBuild(
                repository_url="https://github.com/Microsoft/TypeScript",
                build_command="npm ci && npm test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/tj/commander.js.git",
                build_command="npm ci && npm test && npm run lint",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/expressjs/express.git",
                build_command=dedent(
                    """if [[ "$(npm config get package-lock)" == "true" ]]; then
                    npm config set package-lock false
                else
                    npm config set shrinkwrap false
                fi &&
                npm rm --silent --save-dev connect-redis &&
                npm run test -- --timeout 7500 &&
                npm run lint
                """
                ),
            ),
            GitRepositoryBuild(
                build_command=dedent(
                    """npm -g install yarn &&
                    yarn install &&
                    yarn add react@16 &&
                    yarn run pretest &&
                    yarn run tests-only &&
                    yarn run build
                    """
                ),
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
def test_popular_npm_repos(
    auto_container_per_test: ContainerData,
    container_git_clone: GitRepositoryBuild,
):
    """Try to build and run the tests of a few popular npm packages:

    .. list-table::
       :header-rows: 1

       * - package
         - build command
       * - `chalk <https://github.com/chalk/chalk.git>`_
         - :command:`npm install && npm test`
       * - `Commander.js <https://github.com/tj/commander.js.git>`_
         - :command:`npm ci && npm test && npm run lint`
       * - `Express <https://github.com/expressjs/express.git>`_
         - :command:`npm config set shrinkwrap false && npm rm --silent --save-dev connect-redis && npm run test -- --timeout 7500 && npm run lint`
       * - `prop-types <https://github.com/facebook/prop-types>`_
         - :command:`npm -g install yarn && yarn --frozen-lockfile && yarn run build && yarn run pretest && yarn run tests-only`
       * - `node-fs-extra <https://github.com/jprichardson/node-fs-extra>`_
         - :command:`npm install && npm run unit`

    """
    auto_container_per_test.connection.run_expect(
        [0], container_git_clone.test_command
    )
