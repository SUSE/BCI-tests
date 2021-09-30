import pytest
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import Container
from bci_tester.data import EXTRA_BUILD_ARGS
from bci_tester.data import GO_1_16_BASE_CONTAINER
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import MultiStageBuild
from bci_tester.data import OS_PRETTY_NAME
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = ALL_CONTAINERS

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
    for binary in ("cat", "sh", "bash", "ls", "rm"):
        assert auto_container.connection.exists(binary)


def test_glibc_present(auto_container):
    for binary in ("ldconfig", "ldd"):
        assert auto_container.connection.exists(binary)


@pytest.mark.parametrize(
    "runner",
    [cont for cont in ALL_CONTAINERS if cont != MICRO_CONTAINER]
    + [
        pytest.param(
            MICRO_CONTAINER,
            marks=pytest.mark.xfail(
                reason="Certificates are missing in the micro container"
            ),
        )
    ],
)
def test_certificates_are_present(
    host, tmp_path, container_runtime, runner: Container
):
    multi_stage_build = MultiStageBuild(
        builder=GO_1_16_BASE_CONTAINER,
        runner=runner,
        dockerfile_template=MULTISTAGE_DOCKERFILE,
    )
    multi_stage_build.prepare_build(tmp_path)

    with open(tmp_path / "main.go", "w") as main_go:
        main_go.write(FETCH_SUSE_DOT_COM)

    cmd = host.run_expect(
        [0],
        f"{' '.join(container_runtime.build_command + EXTRA_BUILD_ARGS)} {tmp_path}",
    )
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    host.run_expect(
        [0], f"{container_runtime.runner_binary} run --rm {img_id}"
    )
