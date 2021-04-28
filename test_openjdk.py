import pytest
import subprocess
import testinfra

# def pytest_generate_tests(metafunc):
#     metafunc.parametrize("version_tag",  metafunc.cls.jdks, scope="class")
class MyTester():
    def __init__(self, jdk):
        self.jdk_version = jdk[0]
        self.container_url = jdk[1]
    def get_container(self):
        subprocess.check_call(["echo", "woot", "|", "wall","&&","docker", "pull", self.container_url])  
        docker_id = subprocess.check_output(['docker','run', '-d', '-it', self.container_url, '/bin/sh']).decode().strip()
        yield testinfra.get_host("docker://" + docker_id)
        subprocess.check_call(["docker", 'rm', '-f', docker_id])


@pytest.fixture(scope='module')
def tester(request):
    """ Create a container from containerurl, returns docker_url """
    return MyTester(request.param)

class TestWithDifferentJDKs:
    jdks = [('11','registry.opensuse.org/home/fcrozat/matryoshka/containerfile/opensuse/openjdk:11'),('16','registry.opensuse.org/home/fcrozat/matryoshka/containerfile/opensuse/openjdk:16')]

    @pytest.mark.parametrize('tester', jdks, indirect=['tester'] )
    def test_jdk_version(self, tester):
        host=next(tester.get_container())
        assert "openjdk {}".format(tester.jdk_version) in host.check_output("java --version")

    @pytest.mark.parametrize('tester', jdks, indirect=['tester'] )
    def test_maven_present(self, tester):
        host=next(tester.get_container())
        assert host.run_expect([0],"mvn --version")

    @pytest.mark.parametrize('tester', jdks, indirect=['tester'] )
    def test_maven_present2(self, tester):
        host=next(tester.get_container())
        assert host.run_expect([0],"mvn --version")

    @pytest.mark.parametrize('tester', jdks, indirect=['tester'] )
    def test_maven_present3(self, tester):
        host=next(tester.get_container())
        assert host.run_expect([0],"mvn --version")                