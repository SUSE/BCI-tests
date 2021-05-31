import pytest

from matryoshka_tester.helpers import GitRepositoryBuild


def test_node_version(auto_container):
    assert (
        f"v{auto_container.version}"
        in auto_container.connection.check_output("node -v")
    )
    node_version_from_env = auto_container.connection.run_expect(
        [0], "echo ${NODE_VERSION}"
    ).stdout.strip()
    assert node_version_from_env == auto_container.version, (
        f"mismatch between container version {auto_container.version}) and the"
        f" node version from the environment variable NODE_VERSION "
        f" ({node_version_from_env})"
    )


def test_npm_and_yarn(auto_container):
    assert auto_container.connection.run_expect([0], "npm version")
    installed_yarn_version = auto_container.connection.run_expect(
        [0], "yarn --version"
    ).stdout.strip()
    yarn_version_from_env = auto_container.connection.run_expect(
        [0], "echo ${YARN_VERSION}"
    ).stdout.strip()
    assert installed_yarn_version == yarn_version_from_env, (
        f"Mismatch between installed yarn version {installed_yarn_version} "
        "and the yarn version advertised via "
        f"YARN_VERSION ({yarn_version_from_env})"
    )


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
    print(cmd.stdout)
    print(cmd.stderr)
    assert cmd.rc == 0
