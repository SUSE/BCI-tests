"""Basic tests for the Python base container images."""
import pytest
from bci_tester.data import PYTHON310_CONTAINER
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import PYTHON39_CONTAINER
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import LOCALHOST

bcdir = "/tmp/"
orig = "tests/"
appdir = "trainers/"
outdir = "output/"
appl1 = "tensorflow_examples.py"

# copy tensorflow module trainer from the local application directory to the container
DOCKERF_PY_T = f"""
WORKDIR {bcdir}
RUN mkdir {appdir}
RUN mkdir {outdir}
COPY {orig + appdir}/{appl1}  {appdir}
"""

# Base containers under test, input of auto_container fixture
CONTAINER_IMAGES = [
    PYTHON36_CONTAINER,
    PYTHON39_CONTAINER,
    PYTHON310_CONTAINER,
]

# Derived containers including additional test files, parametrized per test
CONTAINER_IMAGES_T = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(CONTAINER_T),
            containerfile=DOCKERF_PY_T,
        ),
        marks=CONTAINER_T.marks,
        id=CONTAINER_T.id,
    )
    for CONTAINER_T in CONTAINER_IMAGES
]


def test_python_version(auto_container):
    """Test that the python version equals the value from the environment variable
    ``PYTHON_VERSION``.

    """
    reported_version = auto_container.connection.run_expect(
        [0], "python3 --version"
    ).stdout.strip()
    version_from_env = auto_container.connection.run_expect(
        [0], "echo $PYTHON_VERSION"
    ).stdout.strip()

    assert reported_version == f"Python {version_from_env}"


def test_pip(auto_container):
    """Check that :command:`pip` is installed and its version equals the value from
    the environment variable ``PIP_VERSION``.

    """
    assert auto_container.connection.pip.check().rc == 0
    reported_version = auto_container.connection.run_expect(
        [0], "pip --version"
    ).stdout
    version_from_env = auto_container.connection.run_expect(
        [0], "echo $PIP_VERSION"
    ).stdout.strip()

    assert f"pip {version_from_env}" in reported_version


def test_tox(auto_container):
    """Ensure we can use :command:`pip` to install :command:`tox`."""
    auto_container.connection.run_expect([0], "pip install --user tox")


@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_T, indirect=["container_per_test"]
)
def test_python_webserver_1(container_per_test):
    """Test that the python webserver is able to open a given port"""

    port = "8123"

    # pkg neeed to process check
    if not container_per_test.connection.package("iproute2").is_installed:
        container_per_test.connection.run_expect([0], "zypper -n in iproute2")

    # checks that the expected port is Not listening yet
    assert not container_per_test.connection.socket(
        "tcp://0.0.0.0:" + port
    ).is_listening

    # start of the python http server
    bci_pyt_serv = container_per_test.connection.run_expect(
        [0], f"timeout 240s python3 -m http.server {port} &"
    ).stdout

    # checks that the python http.server process is running in the container:
    proc = container_per_test.connection.process.filter(comm="python3")

    # check that the filtered list is not empty
    assert len(proc) > 0, "The python3 http.server process must be running"

    x = None

    for p in proc:
        x = p.args
        if "http.server" in x:
            break

    # checks expected parameter of the running python process
    assert "http.server" in x, "http.server not running."

    # checks that the expected port is listening in the container
    assert container_per_test.connection.socket(
        "tcp://0.0.0.0:" + port
    ).is_listening, "Error on the expected port"


@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_T, indirect=["container_per_test"]
)
def test_python_webserver_2(container_per_test, host, container_runtime):
    """Test that the python `wget <https://pypi.org/project/wget/>`_ library,
    coded in the appl2 module, is able to fetch files from a webserver
    """

    # ID of the running container under test
    c_id = container_per_test.container_id

    destdir = bcdir + outdir

    appl2 = "communication_examples.py"

    url = "https://www.suse.com/assets/img/suse-white-logo-green.svg"

    xfilename = "suse-white-logo-green.svg"

    # install wget for python
    container_per_test.connection.run_expect([0], "pip install wget")

    # copy an application file from the local test-server into the running Container under test
    host.run_expect(
        [0],
        f"{container_runtime.runner_binary} cp {orig + appdir + appl2} {c_id}:{bcdir + appdir}",
    )

    # check the test python module is present in the container
    assert container_per_test.connection.file(bcdir + appdir + appl2).is_file

    # check expected file not present yet in the destination
    assert not container_per_test.connection.file(destdir + xfilename).exists

    # execution of the python module in the container
    bci_python_wget = container_per_test.connection.run_expect(
        [0], f"timeout 240s python3 {appdir + appl2} {url} {destdir}"
    ).stdout

    # run the test in the container and check expected keyword from the module
    assert "PASS" in bci_python_wget

    # check expected file present in the bci destination
    assert container_per_test.connection.file(destdir + xfilename).exists


@pytest.mark.skipif(
    # skip test if architecture is not x86.
    LOCALHOST.system_info.arch != "x86_64",
    reason="Tensorflow python library tested on x86_64",
)
@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_T, indirect=["container_per_test"]
)
def test_tensorf(container_per_test):
    """Test that the python tensorflow library, coded in the appl1 module,
    can be used for ML calculations
    """

    # check the test python module is present in the container
    assert container_per_test.connection.file(bcdir + appdir + appl1).is_file

    # collect CPU flags of the system
    cpuflg = container_per_test.connection.run_expect([0], "lscpu").stdout

    # In precompiled Tensorflow library by default 'sse4' cpu flag expected
    assert "sse4" in cpuflg

    # install TF module for python
    if container_per_test.connection.run("pip install tensorflow").rc != 0:
        pytest.xfail(
            "pip install failure: check tensorflow requirements or update pip"
        )

    # check library import ok
    container_per_test.connection.run_expect(
        [0], 'python3 -c "import tensorflow"'
    )

    # get tf version
    tfver = container_per_test.connection.run_expect(
        [0], 'python3 -c "import tensorflow as tf; print (tf.__version__)"'
    )

    # TensorFlow version: for python 3.x, major tag >= 2
    assert int(tfver.stdout[0]) >= 2

    # Exercise execution running python modules in the container
    testout = container_per_test.connection.run_expect(
        [0], "python3 " + appdir + appl1
    )

    # keyword search
    assert "accuracy" in testout.stdout

    # expected keyword value found: PASS
    assert "PASS" in testout.stdout
