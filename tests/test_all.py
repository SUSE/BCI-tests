"""
This module contains tests that are run for **all** containers.
"""
import pytest
from pytest_container import Container
from pytest_container import get_extra_build_args
from pytest_container import get_extra_run_args
from pytest_container import MultiStageBuild

from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import GO_1_16_CONTAINER
from bci_tester.data import OS_PRETTY_NAME
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = ALL_CONTAINERS

#: go file to perform a GET request to suse.com and that panics if the request
#: fails
FETCH_SUSE_DOT_COM = """package main

import "net/http"

func main() {
	_, err := http.Get("https://suse.com/")
	if err != nil {
		panic(err)
	}
}
"""

MULTISTAGE_DOCKERFILE = """FROM $builder as builder
WORKDIR /src
COPY main.go .
RUN go build main.go

FROM $runner
WORKDIR /fetcher/
COPY --from=builder /src/main .
CMD ["/fetcher/main"]
"""


def test_os_release(auto_container):
    """
    :file:`/etc/os-release` is present and the values of ``OS_VERSION`` and
    ``OS_PRETTY_NAME`` equal :py:const:`bci_tester.data.OS_VERSION` and
    :py:const:`bci_tester.data.OS_PRETTY_NAME` respectively
    """
    assert auto_container.connection.file("/etc/os-release").exists

    for (var_name, value) in (
        ("VERSION_ID", OS_VERSION),
        ("PRETTY_NAME", OS_PRETTY_NAME),
    ):
        assert (
            auto_container.connection.run_expect(
                [0], f". /etc/os-release && echo ${var_name}"
            ).stdout.strip()
            == value
        )


def test_product(auto_container):
    """
    check that :file:`/etc/products.d/SLES.prod` exists and
    :file:`/etc/products.d/baseproduct` is a link to it
    """
    assert auto_container.connection.file("/etc/products.d").is_directory
    assert auto_container.connection.file("/etc/products.d/SLES.prod").is_file
    assert auto_container.connection.file(
        "/etc/products.d/baseproduct"
    ).is_symlink
    assert (
        auto_container.connection.file("/etc/products.d/baseproduct").linked_to
        == "/etc/products.d/SLES.prod"
    )


def test_coreutils_present(auto_container):
    """
    Check that some core utilities (:command:`cat`, :command:`sh`, etc.) exist
    in the container.
    """
    for binary in ("cat", "sh", "bash", "ls", "rm"):
        assert auto_container.connection.exists(binary)


def test_glibc_present(auto_container):
    """ensure that the glibc linker is present"""
    for binary in ("ldconfig", "ldd"):
        assert auto_container.connection.exists(binary)


@pytest.mark.parametrize("runner", ALL_CONTAINERS)
def test_certificates_are_present(
    host, tmp_path, container_runtime, runner: Container, pytestconfig
):
    """This is a multistage container build, verifying that the certificates are
    correctly set up in the containers.

    In the first step, we build a very simple go binary from
    :py:const:`FETCH_SUSE_DOT_COM` in the golang container. We copy the
    resulting binary into the container under test and execute it in that
    container.

    If the certificates are incorrectly set up, then the GET request will fail.
    """
    multi_stage_build = MultiStageBuild(
        containers={"builder": GO_1_16_CONTAINER, "runner": runner},
        containerfile_template=MULTISTAGE_DOCKERFILE,
    )
    multi_stage_build.prepare_build(tmp_path, pytestconfig.rootdir)

    with open(tmp_path / "main.go", "w") as main_go:
        main_go.write(FETCH_SUSE_DOT_COM)

    cmd = host.run_expect(
        [0],
        f"{' '.join(container_runtime.build_command + get_extra_build_args(pytestconfig))} {tmp_path}",
    )
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {' '.join(get_extra_run_args(pytestconfig))} {img_id}",
    )
