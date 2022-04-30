"""Basic tests for the Python 3.6 and 3.9 base container images."""
from pyparsing import MatchFirst
from bci_tester.data import PYTHON310_CONTAINER
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import PYTHON39_CONTAINER

import pytest
from _pytest.mark.structures import ParameterSet
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param

wrk = "/tmp/"
src = "tests/"
rep = "trainers/"
out = "output/"
mtf = "tensorflow_examples.py"

# copy tensorflow module trainer from the local repo to the container
DOCKERF_PY_T = f"""
WORKDIR {wrk}
RUN mkdir {rep}
RUN mkdir {out}
COPY {src + rep}/{mtf}  {rep}
"""

PYTHON36_CONTAINER_T = pytest.param(
    DerivedContainer(
        base=container_from_pytest_param(PYTHON36_CONTAINER),
        containerfile=DOCKERF_PY_T,
    ),
    marks=PYTHON36_CONTAINER.marks,
)

PYTHON39_CONTAINER_T = pytest.param(
    DerivedContainer(
        base=container_from_pytest_param(PYTHON39_CONTAINER),
        containerfile=DOCKERF_PY_T,
    ),
    marks=PYTHON39_CONTAINER.marks,
)

PYTHON310_CONTAINER_T = pytest.param(
    DerivedContainer(
        base=container_from_pytest_param(PYTHON310_CONTAINER),
        containerfile=DOCKERF_PY_T,
    ),
    marks=PYTHON310_CONTAINER.marks,
)

CONTAINER_IMAGES = [
    PYTHON36_CONTAINER_T,
    PYTHON39_CONTAINER_T,
    PYTHON310_CONTAINER_T,
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


def test_python_webserver_1(auto_container_per_test, host, container_runtime):
    """Test that the simple python webserver answers to an internal get request"""

    port = "8123"

    _serv = "nohup timeout 240s python3 -m http.server " + port + " &"

    if not auto_container_per_test.connection.package("iproute2").is_installed:
        auto_container_per_test.connection.run_expect(
            [0], "zypper -n in iproute2"
        )

    # start of the python http server
    auto_container_per_test.connection.run_expect([0], _serv)

    # check for python http.server process running in container
    proc = auto_container_per_test.connection.process.filter(comm="python3")

    x = None

    for p in proc:
        x = p.args
        if "http.server" in x:
            break

    # check keywork present
    assert "http.server" in x, "http.server not running."

    # check of expected port is listening
    assert auto_container_per_test.connection.socket(
        "tcp://0.0.0.0:" + port
    ).is_listening


def test_python_webserver_2(auto_container_per_test, host, container_runtime):
    """Test that the simple python webserver answers to an internal get request"""

    # ID of the running container under test
    c_id = auto_container_per_test.container_id

    outdir = wrk + out

    mpy = "communication_examples.py"

    url = "https://www.suse.com/assets/img/suse-white-logo-green.svg"

    xfilename = "suse-white-logo-green.svg"

    _wget = (
        "timeout 240s python3 "
        + rep
        + mpy
        + " "
        + url
        + " "
        + outdir
    )

    # install wget for python
    auto_container_per_test.connection.run_expect([0], "pip install wget")

    # copy the pythom module in the running Container under test
    host.run_expect(
        [0],
        f"{container_runtime.runner_binary} cp {src + rep + mpy} {c_id}:{wrk + rep + mpy}",
    )

    # check the test python module is present in the container
    assert auto_container_per_test.connection.file(wrk + rep + mpy).is_file

    # check expected file not present yet in the destination
    assert not auto_container_per_test.connection.file(outdir + xfilename).exists

    # run the test in the container and check expected keyword from the module
    assert (
        "PASS"
        in auto_container_per_test.connection.run_expect([0], _wget).stdout
    )

    # check expected file present in the destination
    assert auto_container_per_test.connection.file(outdir + xfilename).exists


def test_tensorf(auto_container_per_test):
    """Test that a tensorflow example works."""

    mpy = "tensorflow_examples.py"

    # commands for tests using python modules in the container, copied from local
    _vers = 'python3 -c "import tensorflow as tf; print (tf.__version__)" 2>&1|tail -1;'

    _test = "timeout 240s python3 " + rep + mpy

    # check the test python module is present in the container
    assert auto_container_per_test.connection.file(wrk + rep + mpy).is_file

    # check the expected CPU flag for TF is available in the system
    flg = auto_container_per_test.connection.run_expect(
        [0], "lscpu| grep -c -i SSE4.. "
    ).stdout

    assert int(flg) > 0

    # install TF module for python
    auto_container_per_test.connection.run_expect(
        [0], "pip install tensorflow"
    )

    ver = auto_container_per_test.connection.run_expect(
        [0], _vers
    ).stdout.strip()

    # TF version: for python 3.x - tf > 2.0
    assert int(ver[0]) >= 2

    # Exercise execution
    xout = auto_container_per_test.connection.run_expect([0], _test)

    # keyword search
    assert "accuracy" in xout.stdout

    # expected keyword value found: PASS
    assert "PASS" in xout.stdout
