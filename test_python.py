def test_python_version(container):
    assert container.version in container.connection.check_output(
        "python --version"
    )


# We don't care about the version, just test that the command seem to work
def test_pip(container):
    assert container.connection.run_expect([0], "pip --version")


# run pip check
def test_recent_pip(container):
    assert container.connection.pip.check().rc == 0


# Ensure we can pip install tox
def test_tox(container):
    assert container.connection.run("pip install --user tox").rc == 0
