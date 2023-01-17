"""Basic tests for the Python base container images."""
import time

import packaging.version
import pytest
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import get_selected_runtime
from pytest_container.runtime import LOCALHOST
from pytest_container.runtime import Version

from bci_tester.data import PYTHON310_CONTAINER
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.runtime_choice import PODMAN_SELECTED

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
EXPOSE {port1}
"""

DOCKERF_PY_T2 = f"""
WORKDIR {bcdir}
RUN mkdir {appdir}
RUN mkdir {outdir}
EXPOSE {port1}
COPY {orig + appdir}/{appl1}  {appdir}
"""

#: Base containers under test, input of auto_container fixture
CONTAINER_IMAGES = [
    PYTHON36_CONTAINER,
    PYTHON310_CONTAINER,
]


#: Derived containers, from custom Dockerfile including additional test files
#: and extra args, input to container_per_test fixture
CONTAINER_IMAGES_T1 = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(CONTAINER_T),
            containerfile=DOCKERF_PY_T1,
            extra_launch_args=["-p", f"{port1}:{port1}"],
        ),
        marks=CONTAINER_T.marks,
        id=CONTAINER_T.id,
    )
    for CONTAINER_T in CONTAINER_IMAGES
]

#: Derived containers, from custom Dockerfile including additional test files,
#: input to container_per_test fixture
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


def test_pip_install_source_cryptography(auto_container_per_test):
    """Check that cryptography python module can be installed from source so that
    it is built against the SLE BCI FIPS enabled libopenssl."""
    version = auto_container_per_test.connection.run_expect(
        [0], "echo $PYTHON_VERSION"
    ).stdout.strip()

    if packaging.version.Version(version) < packaging.version.Version("3.8"):
        pytest.skip("cryptography tests only supported on >= 3.8")

    # install dependencies
    auto_container_per_test.connection.run_expect(
        [0],
        f"zypper --non-interactive in cargo libffi-devel openssl-devel gcc tar gzip",
    )

    # pin cryptography to a version that works with SLE BCI
    cryptography_version = "37.0.4"
    auto_container_per_test.connection.run_expect(
        [0],
        f"pip install --no-binary :all: cryptography=={cryptography_version}",
    )

    # test cryptography
    auto_container_per_test.connection.run_expect(
        [0],
        f"""pip install cryptography-vectors=={cryptography_version} pytest &&
            pip download --no-binary :all: cryptography=={cryptography_version} &&
            tar xf cryptography-{cryptography_version}.tar.gz && cd cryptography-{cryptography_version} &&
            rm -v pyproject.toml &&
            python3 -m pytest tests/hazmat/bindings/test_openssl.py""",
    )


@pytest.mark.skipif(
    PODMAN_SELECTED and get_selected_runtime().version < Version(2, 0),
    reason="server port checks not compatible with old podman versions 1.x",
)
@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_T1, indirect=["container_per_test"]
)
@pytest.mark.parametrize("hmodule, port, retry", [("http.server", port1, 10)])
def test_python_webserver_1(container_per_test, hmodule, port, retry):
    """Test that the python webserver is able to open a given port"""

    portstatus = False

    t = 0

    command = f"timeout --preserve-status 120 python3 -m {hmodule} {port} &"

    # pkg neeed to run socket/port check
    if not container_per_test.connection.package("iproute2").is_installed:
        container_per_test.connection.run_expect([0], "zypper -n in iproute2")

    # checks that the expected port is Not listening yet
    assert not container_per_test.connection.socket(
        f"tcp://0.0.0.0:{port}"
    ).is_listening

    t1 = time.time() - t0

    # start of the python http server
    container_per_test.connection.run_expect([0], command)

    t2 = time.time() - t0

    # port status inspection with timeout
    for t in range(retry):
        time.sleep(1)
        portstatus = container_per_test.connection.socket(
            f"tcp://0.0.0.0:{port}"
        ).is_listening

        if portstatus:
            break

    t3 = time.time() - t0

    # check inspection success or timeout
    assert (
        portstatus
    ), f"Timeout expired: expected port not listening. Time marks: before server start {t1}s, after start {t2}s, after {t} loops {t3}s."


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

    # copy an application file from the local test-server into the running
    # container under test
    host.run_expect(
        [0],
        f"{container_runtime.runner_binary} cp {orig + appdir + appl2} "
        f"{container_per_test.container_id}:{bcdir + appdir}",
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
