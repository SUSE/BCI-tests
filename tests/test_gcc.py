"""Tests for the gcc containers."""

import pytest
from pytest_container import DerivedContainer
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData

from bci_tester.data import GCC_CONTAINERS

CONTAINER_IMAGES = GCC_CONTAINERS

_HELLO_VERSION = "2.12.1"

CONTAINERFILE_HELLO = f"""
WORKDIR /src
RUN curl -sLO https://ftpmirror.gnu.org/hello/hello-{_HELLO_VERSION}.tar.gz && \\
    tar --no-same-permissions --no-same-owner -xf hello-{_HELLO_VERSION}.tar.gz && \\
    cd hello-{_HELLO_VERSION} && \\
    ./configure && \\
    make && \\
    make install
"""

HELLO_CONTAINERS = [
    pytest.param(
        DerivedContainer(
            base=container_and_marks_from_pytest_param(ctr)[0],
            containerfile=CONTAINERFILE_HELLO,
        ),
        marks=ctr.marks,
        id=ctr.id,
    )
    for ctr in CONTAINER_IMAGES
]


@pytest.mark.parametrize("container", HELLO_CONTAINERS, indirect=True)
def test_gcc_container_builds_hello(container: ContainerData) -> None:
    """Test that the gcc container can build GNU hello world."""

    assert (
        container.connection.check_output("hello -g 'Hello SUSE'").strip()
        == "Hello SUSE"
    )
