"""Tests of the OpenJDK base container."""
import os
import re
import time
from dataclasses import dataclass
from dataclasses import field

import pytest
from pytest_container import DerivedContainer
from pytest_container import Version
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER

CONTAINER_TEST_DIR = "/tmp/"
HOST_TEST_DIR = "tests/trainers/java/"

DOCKERF_EXTENDED = f"""
WORKDIR {CONTAINER_TEST_DIR}
COPY {HOST_TEST_DIR} {CONTAINER_TEST_DIR}
"""

DOCKERF_CASSANDRA = """
RUN zypper in -y tar gzip awk git
"""

CONTAINER_IMAGES = [
    OPENJDK_11_CONTAINER,
    OPENJDK_17_CONTAINER,
]

CONTAINER_IMAGES_EXTENDED = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(container),
            containerfile=DOCKERF_EXTENDED,
        ),
        marks=container.marks,
        id=container.id,
    )
    for container in CONTAINER_IMAGES
]

CONTAINER_IMAGES_CASSANDRA = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(container),
            containerfile=DOCKERF_CASSANDRA,
        ),
        marks=container.marks,
        id=container.id,
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
        (
            "memory",
            TestExtendedParams(
                expected_strings=["Iteration: (2)"],
                expected_err_strings=["OutOfMemoryError"],
                expected_exit_status=[1],
                java_params="-Xmx10M",
            ),
        ),
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
    - memory allocation
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
        match = re.search(r"cassandra-(\d).(\d).(\d)$", line)
        if match:
            cur_ver = Version(
                int(match.group(1)), int(match.group(2)), int(match.group(3))
            )
            if cur_ver > cassandra_version:
                cassandra_version = cur_ver

    container_per_test.connection.run_expect(
        [0],
        f"curl -OL https://downloads.apache.org/cassandra/{cassandra_version}/apache-cassandra-{cassandra_version}-bin.tar.gz",
    )

    container_per_test.connection.run_expect(
        [0],
        f"tar xzvf apache-cassandra-{cassandra_version}-bin.tar.gz >/dev/null",
    )

    container_per_test.connection.run_expect(
        [0],
        f"export JAVA_HOME=/usr/ && cd apache-cassandra-{cassandra_version}/ && bin/cassandra -R | tee {logs}",
    )

    check_str = "state jump to NORMAL"
    found = False
    for t in range(80):
        time.sleep(10)
        if (
            check_str
            in container_per_test.connection.file(logs).content_string
        ):
            found = True
            break

    assert found, f"{check_str} not found in {logs}"

    container_per_test.connection.run_expect(
        [0],
        f"export JAVA_HOME=/usr/ && cd apache-cassandra-{cassandra_version}/tools/bin/ && ./cassandra-stress write n=1",
    )

    container_per_test.connection.run_expect(
        [0],
        f"export JAVA_HOME=/usr/ && cd apache-cassandra-{cassandra_version}/tools/bin/ && ./cassandra-stress read n=1",
    )
