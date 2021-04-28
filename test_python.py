import pytest
import subprocess
import testinfra


@pytest.fixture(scope="module")
def host(request):
    image = "registry.opensuse.org/home/dancermak/python/containers_python39/python39:latest"
    subprocess.check_call(["docker", "pull", image])
    docker_id = (
        subprocess.check_output(["docker", "run", "-d", "-it", image, "/bin/sh"])
        .decode()
        .strip()
    )
    yield testinfra.get_host("docker://" + docker_id)
    subprocess.check_call(["docker", "rm", "-f", docker_id])


def test_python_version(host):
    assert "3.9" in host.check_output("python --version")


# We don't care about the version, just test that the command seem to work
def test_pip(host):
    assert host.run_expect([0], "pip --version")


# run pip check
def test_recent_pip(host):
    assert host.pip.check().rc == 0


# Ensure we can pip install tox
def test_tox(host):
    assert host.run("pip install --user tox").rc == 0
