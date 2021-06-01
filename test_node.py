import pytest

from matryoshka_tester.helpers import GitRepositoryBuild


def test_node_version(auto_container):
    assert (
        f"v{auto_container.version}"
        in auto_container.connection.check_output("node -v")
    )


# We don't care about the version, just test that the command seem to work
def test_npm(auto_container):
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
    print(cmd.stdout)
    print(cmd.stderr)
    assert cmd.rc == 0
