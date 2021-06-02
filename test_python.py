def test_python_version(auto_container):
    # output is: Python $version
    version_output = auto_container.connection.check_output("python --version")
    py_version = version_output.split()[1]
    assert auto_container.version in py_version
    assert (
        auto_container.connection.check_output("echo $PYTHON_VERSION")
        == py_version
    )


def test_pip(auto_container):
    # output is: pip $PIP_VER from $PATH (python $PYTHON_VER)
    res = auto_container.connection.run_expect([0], "pip --version")
    pip_ver_from_env = auto_container.connection.check_output(
        "echo $PIP_VERSION"
    )
    entries = res.stdout.strip().split()

    assert entries[0] == "pip", (
        "Unexpected first entry in the output of 'pip --version', "
        f"expected 'pip'. got {entries[0]}"
    )

    assert entries[1] == pip_ver_from_env, (
        f"Got a different pip version from ENV ({pip_ver_from_env}) "
        f"than from pip ({entries[1]})"
    )

    py_ver_of_pip = entries[-1].replace(")", "")
    assert py_ver_of_pip == auto_container.version, (
        f"pip is installed for python {py_ver_of_pip} but this is a "
        f"python {auto_container.version} container"
    )


# run pip check
def test_recent_pip(auto_container):
    assert auto_container.connection.pip.check().rc == 0


# Ensure we can pip install tox
def test_tox(auto_container):
    auto_container.connection.run_expect([0], "pip install --user tox")
