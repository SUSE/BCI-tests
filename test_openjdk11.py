import pytest
import subprocess
import testinfra

@pytest.fixture(scope='module')
def host(request):
    image = "registry.opensuse.org/home/fcrozat/matryoshka/containerfile/opensuse/openjdk:11"
    subprocess.check_call(["docker", "pull", image])
    docker_id = subprocess.check_output(['docker','run', '-d', '-it', image, '/bin/sh']).decode().strip()
    yield testinfra.get_host("docker://" + docker_id)
    subprocess.check_call(["docker", 'rm', '-f', docker_id])

def test_jdk_version(host):
    assert "openjdk 11" in host.check_output("java --version")

def test_maven_present(host):
    assert host.run_expect([0],"mvn --version")