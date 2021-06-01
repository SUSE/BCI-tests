def test_python_version(auto_container):
    assert auto_container.version in auto_container.connection.check_output(
        "python --version"
    )


# We don't care about the version, just test that the command seem to work
def test_pip(auto_container):
    assert auto_container.connection.run_expect([0], "pip --version")


# run pip check
def test_recent_pip(auto_container):
    assert auto_container.connection.pip.check().rc == 0


# Ensure we can pip install tox
def test_tox(auto_container):
    assert auto_container.connection.run("pip install --user tox").rc == 0
