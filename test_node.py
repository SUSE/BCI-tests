import pytest
import testinfra

from conftest import restrict_to_version

# Container fixture contains the black magic to run command on all the different kind of nodes
# per language.
# If you need to run a test for a single version, create your own fixture
# You should think of reusing the `container` fixture from yours.

# The container fixture automatically finds the file from the test, guesses the language, and starts all the necessary containers
# See also conftest.py
def test_node_version(container):
    assert "v{}".format(container.version) in container.connection.check_output(
        "node -v"
    )


# We don't care about the version, just test that the command seem to work
def test_npm(container):
    assert container.connection.run_expect([0], "npm version")


#@restrict_to_version(["14"])
def test_lodash(container):
    cmd = container.connection.run(
        """git clone https://github.com/lodash/lodash.git &&
        cd lodash &&
        npm ci &&
        npm test
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0

# @restrict_to_version(["14"])
def test_chalk(container):
    cmd = container.connection.run(
        """git clone https://github.com/chalk/chalk.git &&
        cd chalk &&
        npm install &&
        npm test
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0


def test_commanderjs(container):
    cmd = container.connection.run(
        """git clone https://github.com/tj/commander.js.git &&
        cd commander.js &&
        npm ci &&
        npm test &&
        npm run lint
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0


def test_visionmediadebug(container):
    cmd = container.connection.run(
        """git clone https://github.com/visionmedia/debug.git &&
        cd debug &&
        npm install &&
        npm run lint &&
        npm run test:node
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0


def test_express(container):
    cmd = container.connection.run(
        """git clone https://github.com/expressjs/express.git &&
        cd express &&
        npm config set shrinkwrap false &&
        npm rm --silent --save-dev connect-redis &&
        npm run test-ci &&
        npm run lint
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0


@pytest.mark.xfail(
    reason="https://github.com/jprichardson/node-fs-extra/issues/898"
)
def test_nodefsextra(container):
    cmd = container.connection.run(
        """git clone https://github.com/jprichardson/node-fs-extra.git &&
        cd node-fs-extra &&
        npm install &&
        npm run unit
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0


def test_moment(container):
    cmd = container.connection.run(
        """git clone https://github.com/moment/moment.git &&
        cd moment &&
        npm install -g grunt-cli &&
        npm install &&
        grunt test
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0


def test_proptypes(container):
    cmd = container.connection.run(
        """git clone https://github.com/facebook/prop-types.git &&
        cd prop-types &&
        yarn install &&
        npm install --no-save "react@~16" "react-dom@~16" &&
        yarn run pretest &&
        yarn run tests-only &&
        yarn run build
        """
    )
    print(cmd.stdout)
    assert cmd.rc == 0
