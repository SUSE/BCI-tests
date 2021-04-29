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


@restrict_to_version(["14"])
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
