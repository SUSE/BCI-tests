from dataclasses import dataclass
from os.path import basename

from typing import Any, Optional

import pytest


@dataclass(frozen=True)
class NpmPackageTest:
    build_command: str = ""
    repository_url: str = ""
    #: an optional tag at which the repository should be checked out instead of
    #: using the default branch
    repository_tag: Optional[str] = None
    marks: Any = None

    @property
    def repo_name(self) -> str:
        return basename(self.repository_url.replace(".git", ""))

    @property
    def test_command(self) -> str:
        checkout_cmd_parts = ["git clone"]
        if self.repository_tag:
            checkout_cmd_parts.append(f"--branch {self.repository_tag}")
        checkout_cmd_parts.append(self.repository_url)

        return f"""{' '.join(checkout_cmd_parts)} &&
            cd {self.repo_name} &&
            {self.build_command}"""

    def __str__(self) -> str:
        return self.repo_name

    def to_pytest_param(self):
        return pytest.param(self, id=self.__str__(), marks=self.marks or ())


def test_node_version(container):
    assert f"v{container.version}" in container.connection.check_output(
        "node -v"
    )


# We don't care about the version, just test that the command seem to work
def test_npm(container):
    assert container.connection.run_expect([0], "npm version")
    assert container.connection.run_expect([0], "yarn --version")


@pytest.mark.parametrize(
    "npm_package",
    [
        pkg.to_pytest_param()
        for pkg in (
            NpmPackageTest(
                repository_url="https://github.com/lodash/lodash.git",
                build_command="npm ci && npm test",
            ),
            NpmPackageTest(
                repository_url="https://github.com/chalk/chalk.git",
                build_command="npm install && npm test",
            ),
            NpmPackageTest(
                repository_url="https://github.com/tj/commander.js.git",
                build_command="npm ci && npm test && npm run lint",
            ),
            NpmPackageTest(
                repository_url="https://github.com/visionmedia/debug.git",
                build_command="""
                    npm install &&
                    npm run lint &&
                    npm run test:node
                    """,
            ),
            NpmPackageTest(
                repository_url="https://github.com/expressjs/express.git",
                build_command="""npm config set shrinkwrap false &&
                    npm rm --silent --save-dev connect-redis &&
                    npm run test-ci &&
                    npm run lint
                    """,
            ),
            NpmPackageTest(
                build_command="""npm install -g grunt-cli &&
                    npm install &&
                    grunt test
                    """,
                repository_url="https://github.com/moment/moment",
            ),
            NpmPackageTest(
                build_command="""yarn install &&
                    npm install --no-save "react@~16" "react-dom@~16" &&
                    yarn run pretest &&
                    yarn run tests-only &&
                    yarn run build
                    """,
                repository_url="https://github.com/facebook/prop-types",
                marks=pytest.mark.skip(reason="Broken for some reason"),
            ),
            NpmPackageTest(
                repository_url="https://github.com/jprichardson/node-fs-extra",
                build_command="npm install && npm run unit",
            ),
        )
    ],
)
def test_popular_npm_repos(container, npm_package: NpmPackageTest):
    cmd = container.connection.run(npm_package.test_command)
    print(cmd.stdout)
    print(cmd.stderr)
    assert cmd.rc == 0
