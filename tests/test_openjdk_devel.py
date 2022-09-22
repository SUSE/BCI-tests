"""Tests for the OpenJDK development container (the container including JDK and
JRE).

"""
import pytest
from pytest_container import DerivedContainer
from pytest_container.container import container_from_pytest_param

from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_17_CONTAINER

CONTAINER_TEST_DIR = "/tmp/"
HOST_TEST_DIR = "tests/trainers/java/"

CONTAINER_IMAGES = [
    OPENJDK_DEVEL_11_CONTAINER,
    OPENJDK_DEVEL_17_CONTAINER,
]

DOCKERF_EXTENDED = f"""
WORKDIR {CONTAINER_TEST_DIR}
COPY {HOST_TEST_DIR} {CONTAINER_TEST_DIR}
"""

# FIXME: once the xfail is removed, use this list to parametrize test_entrypoint
# as well
CONTAINER_IMAGES_EXTENDED = [
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(OPENJDK_DEVEL_11_CONTAINER),
            containerfile=DOCKERF_EXTENDED,
        ),
        marks=OPENJDK_DEVEL_11_CONTAINER.marks,
    ),
    pytest.param(
        DerivedContainer(
            base=container_from_pytest_param(OPENJDK_DEVEL_17_CONTAINER),
            containerfile=DOCKERF_EXTENDED,
        ),
        marks=list(OPENJDK_DEVEL_17_CONTAINER.marks)
        + [
            pytest.mark.xfail(
                reason="https://bugzilla.suse.com/show_bug.cgi?id=1199262"
            )
        ],
    ),
]

# FIXME: once the xfail is removed, use this list to parametrize test_entrypoint
# as well
CONTAINER_IMAGES_WITH_VERSION = [
    pytest.param(
        OPENJDK_DEVEL_11_CONTAINER,
        "11",
        marks=OPENJDK_DEVEL_11_CONTAINER.marks,
    ),
    pytest.param(
        OPENJDK_DEVEL_17_CONTAINER,
        "17",
        marks=list(OPENJDK_DEVEL_17_CONTAINER.marks)
        + [
            pytest.mark.xfail(
                reason="https://bugzilla.suse.com/show_bug.cgi?id=1199262"
            )
        ],
    ),
]


@pytest.mark.parametrize(
    "container,java_version",
    CONTAINER_IMAGES_WITH_VERSION,
    indirect=["container"],
)
def test_jdk_version(container, java_version: str):
    """Ensure that the environment variable ``JAVA_VERSION`` equals the output
    of :command:`javac --version` and :command:`java --version`

    """
    assert f"javac {java_version}" in container.connection.check_output(
        "javac -version"
    )
    assert java_version == container.connection.check_output(
        "echo $JAVA_VERSION"
    )

    assert f"openjdk {java_version}" in container.connection.check_output(
        "java --version"
    )

    assert (
        container.connection.run_expect(
            [0], "echo $JAVA_VERSION"
        ).stdout.strip()
        == java_version
    )


def test_maven_present(auto_container):
    """Check that :command:`maven` is installed and successfully outputs its version
    via :command:`maven --version`.

    """
    assert auto_container.connection.run_expect([0], "mvn --version")


@pytest.mark.parametrize(
    "container,java_version",
    [
        pytest.param(cont, ver, marks=cont.marks)
        for cont, ver in (
            (OPENJDK_DEVEL_11_CONTAINER, "11"),
            (OPENJDK_DEVEL_17_CONTAINER, "17"),
        )
    ],
    indirect=["container"],
)
def test_entrypoint(container, java_version, host, container_runtime):
    """Verify that the entry point of the OpenJDK devel container is the
    :command:`jshell`.

    """
    intro = host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {container.image_url_or_id}",
    ).stdout

    assert "jshell>" in intro
    assert f"Welcome to JShell -- Version {java_version}" in intro


@pytest.mark.parametrize(
    "container",
    CONTAINER_IMAGES_EXTENDED,
    indirect=["container"],
)
@pytest.mark.parametrize(
    "java_file",
    ["Basic"],
)
def test_compile(container, java_file: str):
    """Verify that the entry point of the OpenJDK devel container is the
    :command:`jshell`.

    """
    container.connection.run_expect(
        [0],
        f"ls {CONTAINER_TEST_DIR}{java_file}.java",
    )
    container.connection.run_expect(
        [0],
        "javac --version",
    )
    container.connection.run_expect(
        [0],
        "java --version",
    )
    container.connection.run_expect(
        [0],
        f"javac {CONTAINER_TEST_DIR}{java_file}.java",
    )
    container.connection.run_expect(
        [0],
        f"java -cp {CONTAINER_TEST_DIR} {java_file}",
    )
