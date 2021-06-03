def test_jdk_version(auto_container):
    assert (
        f"javac {auto_container.version}"
        in auto_container.connection.check_output("javac -version")
    )
    assert auto_container.version == auto_container.connection.check_output(
        "echo $JAVA_VERSION"
    )


def test_maven_present(auto_container):
    assert auto_container.connection.run_expect([0], "mvn --version")
