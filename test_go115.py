import pytest
import subprocess
import testinfra

@pytest.fixture(scope='module')
def host(request):
    image = "registry.opensuse.org/home/fcrozat/matryoshka/containerfile/opensuse/golang:1.15"
    subprocess.check_call(["docker", "pull", image])
    docker_id = subprocess.check_output(['docker','run', '-d', '-it', image, '/bin/sh']).decode().strip()
    yield testinfra.get_host("docker://" + docker_id)
    subprocess.check_call(["docker", 'rm', '-f', docker_id])

def test_go_version(host):
    assert "1.15" in host.check_output("go version")