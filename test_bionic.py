import pytest
import subprocess
import testinfra

# All the tests of this should use a single container
# If need to move towards one test per container, remove
# scope='module' to default back to scope='function'
# NB: We've pulled the image beforehand, so the docker-run should be almost instant.
# NB2: If the docker pull is _NOT_ in the tox.ini, make sure your pull the image if you want to run on scope='function'.
@pytest.fixture(scope="module")
def host(request):
    image = "ubuntu:bionic"
    docker_id = (
        subprocess.check_output(
            ["docker", "run", "-d", "-it", image, "/bin/sh"]
        )
        .decode()
        .strip()
    )
    yield testinfra.get_host("docker://" + docker_id)
    subprocess.check_call(["docker", "rm", "-f", docker_id])


def test_passwd_present(host):
    assert host.file("/etc/passwd").exists


def test_bash_present(host):
    assert host.file("/bin/bash").exists
