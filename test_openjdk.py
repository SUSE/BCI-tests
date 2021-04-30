import os.path
import subprocess

import pytest
import testinfra


def test_jdk_version(container):
    assert "openjdk {}".format(container.version) in container.connection.check_output(
        "java --version"
    )


def test_maven_present(container):
    assert container.connection.run_expect([0], "mvn --version")


@pytest.mark.git("https://github.com/paketo-buildpacks/samples")
def test_pack_java_maven(gitclone):
    cmd = subprocess.run(
        "pack build pack-java-maven --builder paketobuildpacks/builder:base",
        shell=True,
        cwd=os.path.join(gitclone, "java", "maven"),
    )
    assert cmd.returncode == 0
