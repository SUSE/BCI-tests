from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import PYTHON39_CONTAINER


CONTAINER_IMAGES = [PYTHON36_CONTAINER, PYTHON39_CONTAINER]


def test_python_version(auto_container):
    reported_version = auto_container.connection.run_expect(
        [0], "python3 --version"
    ).stdout.strip()
    version_from_env = auto_container.connection.run_expect(
        [0], "echo $PYTHON_VERSION"
    ).stdout.strip()

    assert reported_version == f"Python {version_from_env}"


def test_pip(auto_container):
    assert auto_container.connection.pip.check().rc == 0
    reported_version = auto_container.connection.run_expect(
        [0], "pip --version"
    ).stdout
    version_from_env = auto_container.connection.run_expect(
        [0], "echo $PIP_VERSION"
    ).stdout.strip()

    assert f"pip {version_from_env}" in reported_version


def test_tox(auto_container):
    """Ensure we can pip install tox"""
    auto_container.connection.run_expect([0], "pip install --user tox")
