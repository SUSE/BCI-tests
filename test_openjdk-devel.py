def test_jdk_version(container):
    assert f"javac {container.version}" in container.connection.check_output(
        "javac -version"
    )


def test_maven_present(container):
    assert container.connection.run_expect([0], "mvn --version")
