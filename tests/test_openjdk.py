"""Tests of the OpenJDK base container."""

import os.path
import re
import time
from dataclasses import dataclass
from dataclasses import field

import pytest
from pytest_container import DerivedContainer
from pytest_container import Version
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER
from bci_tester.data import OPENJDK_21_CONTAINER
from bci_tester.data import OPENJDK_23_CONTAINER

CONTAINER_TEST_DIR = "/tmp/"
HOST_TEST_DIR = "tests/trainers/java/"

DOCKERF_EXTENDED = f"""
WORKDIR {CONTAINER_TEST_DIR}
COPY {HOST_TEST_DIR} {CONTAINER_TEST_DIR}
"""

DOCKERF_CASSANDRA = """
RUN zypper -n in tar gzip git-core util-linux
"""

DOCKERFILE_OPENJDK_FIPS = """WORKDIR /src/
COPY tests/files/Tcheck.java tests/files/JCEProviderInfo.java /src/
ENV NSS_FIPS 1
RUN zypper -n in mozilla-nss* java-$JAVA_VERSION-openjdk-devel
"""

FIPS_OPENJDK_IMAGES = []

for ctr in [OPENJDK_17_CONTAINER, OPENJDK_21_CONTAINER]:
    FIPS_OPENJDK_IMAGES.append(
        DerivedContainer(containerfile=DOCKERFILE_OPENJDK_FIPS, base=ctr)
    )

CONTAINER_IMAGES = [
    OPENJDK_11_CONTAINER,
    OPENJDK_17_CONTAINER,
    OPENJDK_21_CONTAINER,
    OPENJDK_23_CONTAINER,
]

CONTAINER_IMAGES_EXTENDED = [
    DerivedContainer(
        base=container,
        containerfile=DOCKERF_EXTENDED,
    )
    for container in CONTAINER_IMAGES
]

CONTAINER_IMAGES_CASSANDRA = [
    DerivedContainer(
        base=container,
        containerfile=DOCKERF_CASSANDRA,
    )
    for container in [OPENJDK_11_CONTAINER]
]


@pytest.mark.parametrize(
    "container,java_version",
    [
        pytest.param(
            OPENJDK_11_CONTAINER, "11", marks=OPENJDK_11_CONTAINER.marks
        ),
        pytest.param(
            OPENJDK_17_CONTAINER, "17", marks=OPENJDK_17_CONTAINER.marks
        ),
        pytest.param(
            OPENJDK_21_CONTAINER, "21", marks=OPENJDK_21_CONTAINER.marks
        ),
        pytest.param(
            OPENJDK_23_CONTAINER, "23", marks=OPENJDK_23_CONTAINER.marks
        ),
    ],
    indirect=["container"],
)
def test_jdk_version(container, java_version):
    """Check that the environment variable ``JAVA_VERSION`` is equal to the output
    of :command:`java --version`.

    """
    assert f"openjdk {java_version}" in container.connection.check_output(
        "java --version"
    )

    assert (
        container.connection.check_output("echo $JAVA_VERSION") == java_version
    )


def test_java_home(auto_container: ContainerData):
    """Check that the environment variable ``JAVA_HOME`` is set to the correct
    value.

    - check that ``JAVA_HOME`` is a directory
    - check that ``JAVA_ROOT`` is a directory
    - check that ``JAVA_BINDIR`` is a directory and that it contains the
      executable :command:`java`.
    - parse the output of :command:`java -XshowSettings:properties -version`,
      extract the setting ``java.home`` and compare it to ``JAVA_HOME``

    Regression test following https://bugzilla.suse.com/show_bug.cgi?id=1206128

    """

    def get_env_var(var: str) -> str:
        return auto_container.connection.check_output(f"echo ${var}").strip()

    java_home_path = get_env_var("JAVA_HOME")
    java_home = auto_container.connection.file(java_home_path)
    assert java_home.exists and java_home.is_directory

    java_root = auto_container.connection.file(get_env_var("JAVA_ROOT"))
    assert java_root.exists and java_root.is_directory

    java_bindir_path = get_env_var("JAVA_BINDIR")
    java_bindir = auto_container.connection.file(java_bindir_path)
    assert java_bindir.exists and java_bindir.is_directory

    auto_container.connection.file(os.path.join(java_bindir_path, "java"))
    auto_container.connection.check_output(
        f"{os.path.join(java_bindir_path, 'java')} --version"
    )

    java_props_cmd = "java -XshowSettings:properties -version"
    java_properties = auto_container.connection.run_expect(
        [0], java_props_cmd
    ).stderr.strip()
    java_home_setting_checked = False
    for line in java_properties.splitlines():
        if line.strip().startswith("java.home"):
            assert line.strip().replace("java.home = ", "") == java_home_path
            java_home_setting_checked = True
    assert java_home_setting_checked, (
        f"java.home setting missing in the output of {java_props_cmd}"
    )


@dataclass(frozen=True)
class TestExtendedParams:
    """
    A class used to pass parameters and options to test_jdk_extended

    Attributes:
        expected_strings Expected standard output strings
        expected_err_strings Expected standard error strings
        expected_exit_status Expected list of allowed exit codes
        java_params java runtime parameters as they would be passed on the CLI
        arguments arguments to pass to the java test
        environment environment variables in the form ``VAR=foo VAR2=bar``
    """

    expected_strings: list = field(default_factory=lambda: [])
    expected_err_strings: list = field(default_factory=lambda: [])
    expected_exit_status: list = field(default_factory=lambda: [0])
    java_params: str = ""
    arguments: str = ""
    environment: str = ""


@pytest.mark.parametrize(
    "container_per_test",
    CONTAINER_IMAGES_EXTENDED,
    indirect=["container_per_test"],
)
@pytest.mark.parametrize(
    "test_to_run, params",
    [
        (
            "threads_concurrency_and_sleep",
            TestExtendedParams(
                expected_strings=["I am the thread 1", "I am the thread 2"]
            ),
        ),
        ("time", TestExtendedParams(expected_strings=["All OK"])),
        ("garbage_collector", TestExtendedParams()),
        (
            "system_exit",
            TestExtendedParams(expected_exit_status=[2], arguments="2"),
        ),
        (
            "system_env",
            TestExtendedParams(
                expected_strings=["test"], environment="ENV1=test"
            ),
        ),
        (
            "subprocesses",
            TestExtendedParams(expected_strings=["tmp", "usr"]),
        ),
    ],
)
def test_jdk_extended(
    container_per_test,
    test_to_run: str,
    params: TestExtendedParams,
):
    """Executes a set of java files stored on test/trainers/java/ directory.
    It covers:
    - threading tests
    - java time and date tests
    - files and dirs tests
    - garbage collector
    - system module (env, exit, properties)
    - subprocesses
    The validation is done checking the exit code (0) and checking that some
    expected strings can be found on the stdout of the execution.
    """
    cmd = f"{params.environment} java {params.java_params} {CONTAINER_TEST_DIR}{test_to_run}.java {params.arguments}"
    testout = container_per_test.connection.run_expect(
        params.expected_exit_status, cmd
    )

    for check in params.expected_strings:
        assert check in testout.stdout

    for check in params.expected_err_strings:
        assert check in testout.stderr


@pytest.mark.skipif(
    LOCALHOST.system_info.arch == "ppc64le",
    reason="Cassandra test skipped for PPC architecture. See https://progress.opensuse.org/issues/119344",
)
@pytest.mark.parametrize(
    "container_per_test",
    CONTAINER_IMAGES_CASSANDRA,
    indirect=["container_per_test"],
)
def test_jdk_cassandra(container_per_test):
    """Starts the Cassandra DB and executes some write and read tests
    using the cassandra-stress
    """

    logs = "/var/log/cassandra.log"

    cassandra_versions = container_per_test.connection.check_output(
        "git ls-remote --tags https://gitbox.apache.org/repos/asf/cassandra.git"
    )

    cassandra_version = Version(0, 0, 0)
    for line in cassandra_versions.splitlines():
        match = re.search(r"cassandra-(\d+)\.(\d+)\.(\d+)$", line)
        if match:
            cur_ver = Version(
                int(match.group(1)), int(match.group(2)), int(match.group(3))
            )
            cassandra_version = max(cur_ver, cassandra_version)

    cassandra_base = f"apache-cassandra-{cassandra_version}"
    container_per_test.connection.check_output(
        f"cd /tmp && curl -sfOL https://downloads.apache.org/cassandra/{cassandra_version}/{cassandra_base}-bin.tar.gz",
    )
    container_per_test.connection.check_output(
        f"cd /tmp && tar --no-same-permissions --no-same-owner -xf {cassandra_base}-bin.tar.gz",
    )
    container_per_test.connection.check_output(
        f"cd /tmp/{cassandra_base}/ && bin/cassandra -R | tee {logs}",
    )

    check_str = "state jump to NORMAL"
    found = False
    for _ in range(80):
        time.sleep(10)
        if (
            check_str
            in container_per_test.connection.file(logs).content_string
        ):
            found = True
            break

    assert found, f"{check_str} not found in {logs}"

    container_per_test.connection.check_output(
        f"cd /tmp/{cassandra_base}/tools/bin/ && ./cassandra-stress write n=1 && ./cassandra-stress read n=1",
    )


@pytest.mark.parametrize(
    "container_per_test",
    FIPS_OPENJDK_IMAGES,
    indirect=True,
)
def test_openjdk_sec_providers(container_per_test: ContainerData) -> None:
    """
    Verifies that the primary security provider in FIPS-enabled OpenJDK
    containers is `SunPKCS11-NSS-FIPS`. The test uses Java scripts to list and
    validate security providers, ensuring FIPS compliance.
    """
    c = container_per_test.connection
    c.check_output("java JCEProviderInfo.java")
    assert "1. SunPKCS11-NSS-FIPS" in c.check_output("java Tcheck.java")
