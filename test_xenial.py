import pytest
import subprocess
import testinfra

@pytest.fixture(scope='module')
def host(request):
    image = "ubuntu:xenial"
    docker_id = subprocess.check_output(['docker','run', '-d', '-it', image, '/bin/sh']).decode().strip()
    yield testinfra.get_host("docker://" + docker_id)
    subprocess.check_call(["docker", 'rm', '-f', docker_id])

def test_passwd_present(host):
    assert host.file("/etc/passwd").exists

def test_bash_present2(host):
    assert host.file("/bin/bash").exists