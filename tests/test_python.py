"""Basic tests for the Python base container images."""
import time

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
port1 = 8123
t0 = time.time()

# copy tensorflow module trainer from the local application directory to the container
DOCKERF_PY_T1 = f"""
WORKDIR {bcdir}
COPY {orig + appdir}/{appl1}  {bcdir}
EXPOSE {port1}
"""

DOCKERF_PY_T2 = f"""
WORKDIR {bcdir}
RUN mkdir {appdir}
RUN mkdir {outdir}
EXPOSE {port1}
COPY {orig + appdir}/{appl1}  {appdir}
"""

# Base containers under test, input of auto_container fixture
CONTAINER_IMAGES = [
    PYTHON36_CONTAINER,
    PYTHON39_CONTAINER,
    PYTHON310_CONTAINER,
]


# Derived containers, from custom Dockerfile including additional test files and extra args, input to container_per_test fixture
CONTAINER_IMAGES_T1 = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(CONTAINER_T),
            containerfile=DOCKERF_PY_T1,
            extra_launch_args=["-d", "-p", f"{port1}:{port1}"],
        ),
        marks=CONTAINER_T.marks,
        id=CONTAINER_T.id,
    )
    for CONTAINER_T in CONTAINER_IMAGES
]

# Derived containers, from custom Dockerfile including additional test files, input to container_per_test fixture
CONTAINER_IMAGES_T2 = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(CONTAINER_T),
            containerfile=DOCKERF_PY_T2,
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
    "container_per_test", CONTAINER_IMAGES_T1, indirect=["container_per_test"]
)
@pytest.mark.parametrize("hmodule, port, retry", [("http.server", port1, 10)])
def test_python_webserver_1(container_per_test, hmodule, port, retry):
    """Test that the python webserver is able to open a given port"""

    portstatus = False

    t = 0

    # pkg neeed to run socket/port check
    if not container_per_test.connection.package("iproute2").is_installed:
        container_per_test.connection.run_expect([0], "zypper -n in iproute2")

    #p2=LOCALHOST.socket(f"tcp://127.0.0.1:{port}").is_listening
    # p3=LOCALHOST.run_expect([0], f"curl http://127.0.0.1:{port}")
    # p3=LOCALHOST.run(f"timeout --preserve-status 30 wget http://127.0.0.1:{port}/{appl1}")
    #print("ante start", p2) #, p3.stdout)

    # checks that the expected port is Not listening yet
    assert not container_per_test.connection.socket(
        f"tcp://0.0.0.0:{port}"
    ).is_listening

    t1 = time.time() - t0

    # command = "ss --numeric --listening --tcp |grep 8123;echo before;" + f"(timeout --preserve-status 30 python3 -m {hmodule} {port} &); " + "sleep 2;echo after;" + "ss --numeric --listening --tcp |grep 8123;" 
    command = f"(timeout --preserve-status 30 python3 -m {hmodule} {port} &);"
    
    # start of the python http server
    container_per_test.connection.run_expect(
        [0], command
    )

    #container_per_test.connection.run_expect(
    #    [0], f"timeout --preserve-status 30 python3 -m {hmodule} {port} &"
    #)

    t1b = time.time() - t0

    #p2=LOCALHOST.socket(f"tcp://127.0.0.1:{port}").is_listening
    # p3=LOCALHOST.run_expect([0], f"curl http://127.0.0.1:{port}")
    # p3=LOCALHOST.run_expect([0], f"timeout --preserve-status 30 wget http://127.0.0.1:{port}/{appl1}")
    #print("post start", p2) #, p3.stdout)
    
    # port status inspection with timeout
    for t in range(retry):
        time.sleep(1)
        portstatus = container_per_test.connection.socket(
            f"tcp://0.0.0.0:{port}"
        ).is_listening
        print (t,time.time() - t0)

        if portstatus:
            break
    
    x = container_per_test.connection.run_expect([0], "ps ax | grep python")

    t2 = time.time() - t0

    # check inspection success or timeout
    assert (
        portstatus
    ), f"Timeout expired:Before start {t1}-{t1b}s After {t} checks {t2}s. Expected port not listening"


@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_T2, indirect=["container_per_test"]
)
@pytest.mark.parametrize(
    "destdir, appl2, url, xfilename",
    [
        (
            bcdir + outdir,
            "communication_examples.py",
            "https://www.suse.com/assets/img/suse-white-logo-green.svg",
            "suse-white-logo-green.svg",
        )
    ],
)
def test_python_webserver_2(
    container_per_test, host, container_runtime, destdir, appl2, url, xfilename
):
    """Test that the python `wget <https://pypi.org/project/wget/>`_ library,
    coded in the appl2 module, is able to fetch files from a webserver
    """

    # install wget for python
    container_per_test.connection.run_expect([0], "pip install wget")

    # copy an application file from the local test-server into the running Container under test
    host.run_expect(
        [0],
        f"{container_runtime.runner_binary} cp {orig + appdir + appl2} {container_per_test.container_id}:{bcdir + appdir}",
    )

    # check the test python module is present in the container
    assert container_per_test.connection.file(bcdir + appdir + appl2).is_file

    # check expected file not present yet in the destination
    assert not container_per_test.connection.file(destdir + xfilename).exists

    # execution of the python module in the container
    bci_python_wget = container_per_test.connection.run_expect(
        [0],
        f"timeout --preserve-status 120s python3 {appdir + appl2} {url} {destdir}",
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
    "container_per_test", CONTAINER_IMAGES_T2, indirect=["container_per_test"]
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

    # TensorFlow version format check
    assert tfver.stdout.split(".")[0].isnumeric()

    # TensorFlow version: for python 3.x, major tag >= 2
    assert int(tfver.stdout.split(".")[0]) >= 2

    # Exercise execution running python modules in the container
    testout = container_per_test.connection.run_expect(
        [0], "python3 " + appdir + appl1
    )

    # keyword search
    assert "accuracy" in testout.stdout

    # expected keyword value found: PASS
    assert "PASS" in testout.stdout
