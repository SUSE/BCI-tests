def test_jdk_version(auto_container):
    assert "openjdk {}".format(
        auto_container.version
    ) in auto_container.connection.check_output("java --version")

    assert auto_container.version == auto_container.connection.check_output(
        "echo $JAVA_VERSION"
    )
