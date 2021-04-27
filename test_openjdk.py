import pytest
import subprocess
import testinfra

def pytest_generate_tests(metafunc):
    metafunc.parametrize("jdk",  metafunc.cls.jdks, scope="class")


class TestWithDifferentJDKs:
    jdks = [11, 16]
    container_location = 'registry.opensuse.org/home/fcrozat/matryoshka/containerfile/opensuse/openjdk'         

    @pytest.fixture
    def host(self, jdk):
        image = self.container_location + ':{}'.format(jdk)
        subprocess.check_call(["docker", "pull", image])  
        docker_id = subprocess.check_output(['docker','run', '-d', '-it', image, '/bin/sh']).decode().strip()
        yield testinfra.get_host("docker://" + docker_id)
        subprocess.check_call(["docker", 'rm', '-f', docker_id])

    def test_jdk_version(self, jdk, host):
        assert "openjdk {}".format(jdk) in host.check_output("java --version")

    def test_maven_present(self, host):
        assert host.run_expect([0],"mvn --version")

    def test_maven_present2(self, host):
        assert host.run_expect([0],"mvn --version")
    def test_maven_present3(self, host):
        assert host.run_expect([0],"mvn --version")                