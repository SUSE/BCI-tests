from bci_tester.data import PYTHON36_CONTAINER, PYTHON39_CONTAINER


CONTAINER_IMAGES = [PYTHON36_CONTAINER, PYTHON39_CONTAINER]


def test_python_version(auto_container):
    auto_container.connection.run_expect([0], "python3 --version")


def test_pip(auto_container):
    assert auto_container.connection.pip.check().rc == 0
    auto_container.connection.run_expect([0], "pip --version")


def test_tox(auto_container):
    """Ensure we can pip install tox"""
    auto_container.connection.run_expect([0], "pip install --user tox")
