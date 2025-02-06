"""Basic tests for the Python base container images."""

import time

import packaging.version
import pytest
import requests
from pytest_container import DerivedContainer
from pytest_container import OciRuntimeBase
from pytest_container import PortForwarding
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import LOCALHOST
from pytest_container.runtime import Version
from pytest_container.runtime import get_selected_runtime

from bci_tester.data import OS_VERSION
from bci_tester.data import PYTHON_CONTAINERS
from bci_tester.data import PYTHON_WITH_PIPX_CONTAINERS
from bci_tester.data import SAC_PYTHON_CONTAINERS
from bci_tester.runtime_choice import PODMAN_SELECTED

BCDIR = "/tmp/"
ORIG = "tests/"
APPDIR = "trainers/"
OUTDIR = "output/"
APPL1 = "tensorflow_examples.py"
PORT1 = 8123
t0 = time.time()


DOCKERF_PY_T2 = f"""
WORKDIR {BCDIR}
RUN mkdir {APPDIR}
RUN mkdir {OUTDIR}
EXPOSE {PORT1}
COPY {ORIG + APPDIR}/{APPL1}  {APPDIR}
"""

#: Base containers under test, input of auto_container fixture
CONTAINER_IMAGES = PYTHON_CONTAINERS + SAC_PYTHON_CONTAINERS


#: Derived containers with the python http.server as CMD and a HEALTHCHECK
#: ensuring that the server is up and running
HTTP_SERVER_CONTAINER_IMAGES = [
    pytest.param(
        DerivedContainer(
            base=container_and_marks_from_pytest_param(CONTAINER_T)[0],
            containerfile=f"""RUN zypper -n in iproute2 curl && zypper -n clean
CMD python3 -m http.server {PORT1}
HEALTHCHECK --interval=10s --timeout=1s --retries=10 CMD curl -sf http://localhost:{PORT1}
""",
            forwarded_ports=[PortForwarding(container_port=PORT1)],
            image_format=ImageFormat.DOCKER,
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
            base=container_and_marks_from_pytest_param(CONTAINER_T)[0],
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
    reported_version = auto_container.connection.check_output(
        "python3 --version"
    )
    version_from_env = auto_container.connection.check_output(
        "echo $PYTHON_VERSION"
    )

    assert reported_version == f"Python {version_from_env}"


@pytest.mark.parametrize(
    "container_per_test",
    PYTHON_WITH_PIPX_CONTAINERS,
    indirect=["container_per_test"],
)
def test_pipx(container_per_test):
    """Test that we can install xkcdpass via :command:`pipx`."""
    container_per_test.connection.check_output("pipx install xkcdpass")
    assert "xkcdpass" in container_per_test.connection.check_output(
        "pipx list --short"
    )
    run1 = container_per_test.connection.check_output("xkcdpass")
    run2 = container_per_test.connection.check_output("xkcdpass")
    assert len(run1) > 20 and len(run2) > 20, (
        "xkcdpass should output a passphrase with more than 20 characters"
    )
    assert run1 != run2, (
        "xkcdpass should output a different passphrase each time"
    )


def test_pip(auto_container):
    """Check that :command:`pip` is installed and its version equals the value from
    the environment variable ``PIP_VERSION``.

    """
    assert auto_container.connection.pip.check().rc == 0
    reported_version = auto_container.connection.check_output("pip --version")
    version_from_env = auto_container.connection.check_output(
        "echo $PIP_VERSION"
    )

    assert f"pip {version_from_env}" in reported_version


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="pip --user not working due to PEP 668",
)
def test_tox(auto_container_per_test):
    """Ensure we can use :command:`pip` to install :command:`tox`."""
    auto_container_per_test.connection.run_expect(
        [0], "pip install --user tox"
    )


def test_pep517_wheels(auto_container_per_test):
    """Ensure we can use :command:`pip` to build PEP517 binary wheels"""
    version = auto_container_per_test.connection.check_output(
        "echo $PYTHON_VERSION"
    )
    if "3.12" in version and OS_VERSION not in ("tumbleweed",):
        pytest.skip(
            "SLEs python 3.12 currently does not provide python312-wheel"
        )
    if packaging.version.Version(version) < packaging.version.Version("3.10"):
        pytest.skip("ujson pep517 only supported on Python >= 3.10")

    pip_install = "pip install"
    if OS_VERSION in ("tumbleweed",):
        pip_install += " --break-system-packages --user"
    ujson_version = "5.10.0"
    auto_container_per_test.connection.check_output(
        "zypper -n install gcc-c++ && "
        f"pip download --no-deps --no-binary :all: ujson=={ujson_version} && "
        f"tar --no-same-permissions --no-same-owner -xf ujson-{ujson_version}.tar.gz && "
        f"cd ujson-{ujson_version} && "
        f"{pip_install} setuptools_scm && "
        "pip wheel --use-pep517 --no-build-isolation --no-deps -w $PWD . && "
        f"{pip_install} ujson-{ujson_version}-*.whl && "
        "python3 -c 'import ujson'"
    )


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="pip --user not working due to PEP 668",
)
def test_pip_install_source_cryptography(auto_container_per_test):
    """Check that cryptography python module can be installed from source so that
    it is built against the SLE BCI FIPS enabled libopenssl."""
    version = auto_container_per_test.connection.check_output(
        "echo $PYTHON_VERSION"
    )

    if packaging.version.Version(version) < packaging.version.Version("3.10"):
        pytest.skip("cryptography tests only supported on >= 3.10")

    # install dependencies
    auto_container_per_test.connection.run_expect(
        [0],
        "zypper --non-interactive in cargo libffi-devel openssl-devel gcc tar gzip",
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
    "container_per_test", HTTP_SERVER_CONTAINER_IMAGES, indirect=True
)
def test_python_http_server_module(container_per_test: ContainerData) -> None:
    """Test that the python webserver is able to open a given port"""

    ctr_port = container_per_test.forwarded_ports[0].container_port
    host_port = container_per_test.forwarded_ports[0].host_port

    assert container_per_test.connection.socket(
        f"tcp://0.0.0.0:{ctr_port}"
    ).is_listening

    resp = requests.get(f"http://0.0.0.0:{host_port}", timeout=10)
    resp.raise_for_status()
    assert resp.text


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="pip --user not working due to PEP 668",
)
@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_T2, indirect=["container_per_test"]
)
@pytest.mark.parametrize(
    "destdir, appl2, url, xfilename",
    [
        (
            BCDIR + OUTDIR,
            "communication_examples.py",
            "https://opensource.suse.com/bci/SLE_BCI_logomark_green.svg",
            "SLE_BCI_logomark_green.svg",
        )
    ],
)
def test_python_webserver_2(
    container_per_test: ContainerData,
    host,
    container_runtime: OciRuntimeBase,
    destdir: str,
    appl2: str,
    url: str,
    xfilename: str,
) -> None:
    """Test that the python `wget <https://pypi.org/project/wget/>`_ library,
    coded in the appl2 module, is able to fetch files from a webserver
    """

    # install wget for python
    container_per_test.connection.run_expect([0], "pip install wget")

    # copy an application file from the local test-server into the running
    # container under test
    host.check_output(
        f"{container_runtime.runner_binary} cp {ORIG + APPDIR + appl2} "
        f"{container_per_test.container_id}:{BCDIR + APPDIR}",
    )

    # check the test python module is present in the container
    assert container_per_test.connection.file(BCDIR + APPDIR + appl2).is_file

    # check expected file not present yet in the destination
    assert not container_per_test.connection.file(destdir + xfilename).exists

    # execution of the python module in the container
    bci_python_wget = container_per_test.connection.check_output(
        f"timeout --preserve-status 120s python3 {APPDIR + appl2} {url} {destdir}",
    )

    # run the test in the container and check expected keyword from the module
    assert "PASS" in bci_python_wget

    # check expected file present in the bci destination
    assert container_per_test.connection.file(destdir + xfilename).exists


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="pip --user not working due to PEP 668",
)
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
    assert container_per_test.connection.file(BCDIR + APPDIR + APPL1).is_file

    # collect CPU flags of the system
    cpuflg = container_per_test.connection.file("/proc/cpuinfo").content_string

    # In precompiled Tensorflow library by default 'sse4' cpu flag expected
    assert "sse4" in cpuflg

    # install TF module for python
    if (
        container_per_test.connection.run("pip install --user tensorflow").rc
        != 0
    ):
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
        [0], "python3 " + APPDIR + APPL1
    )

    # keyword search
    assert "accuracy" in testout.stdout

    # expected keyword value found: PASS
    assert "PASS" in testout.stdout
