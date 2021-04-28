import pytest
import subprocess
import testinfra


@pytest.fixture(scope="module")
def host(request):
    image = (
        "registry.opensuse.org/home/dancermak/nodejs/containers_node15/node15:latest"
    )
    subprocess.check_call(["docker", "pull", image])
    docker_id = (
        subprocess.check_output(["docker", "run", "-d", "-it", image, "/bin/sh"])
        .decode()
        .strip()
    )
    yield testinfra.get_host("docker://" + docker_id)
    subprocess.check_call(["docker", "rm", "-f", docker_id])


def test_node_version(host):
    assert "v15" in host.check_output("node -v")


# We don't care about the version, just test that the command seem to work
def test_npm(host):
    assert host.run_expect([0], "npm version")
