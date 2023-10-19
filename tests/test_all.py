"""
This module contains tests that are run for **all** containers.
"""
import datetime
import fnmatch
import xml.etree.ElementTree as ET

import pytest
from _pytest.config import Config
from pytest_container import Container
from pytest_container import get_extra_build_args
from pytest_container import get_extra_run_args
from pytest_container import MultiStageBuild
from pytest_container.container import ContainerData

from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import OS_PRETTY_NAME
from bci_tester.data import OS_VERSION
from bci_tester.data import OS_VERSION_ID
from bci_tester.data import PCP_CONTAINER
from bci_tester.data import POSTGRESQL_CONTAINERS

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
ENTRYPOINT []
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

    for var_name, expected_value in (
        ("VERSION_ID", OS_VERSION_ID),
        ("PRETTY_NAME", OS_PRETTY_NAME),
    ):
        if var_name == "VERSION_ID":
            if OS_VERSION == "tumbleweed":
                # on openSUSE Tumbleweed that is the an ever changing snapshot date
                # just check whether it is less than 10 days old
                assert (
                    datetime.datetime.now()
                    - datetime.datetime.strptime(
                        auto_container.connection.run_expect(
                            [0], f". /etc/os-release && echo ${var_name}"
                        ).stdout.strip(),
                        "%Y%m%d",
                    )
                ).days < 10
                continue

        assert (
            auto_container.connection.run_expect(
                [0], f". /etc/os-release && echo ${var_name}"
            ).stdout.strip()
            == expected_value
        )


def test_product(auto_container):
    """
    check that :file:`/etc/products.d/$BASEPRODUCT.prod` exists and
    :file:`/etc/products.d/baseproduct` is a link to it
    """
    assert auto_container.connection.file("/etc/products.d").is_directory
    prodfname = "SLES"
    if OS_VERSION == "tumbleweed":
        prodfname = "openSUSE"
    if OS_VERSION == "basalt":
        prodfname = "ALP"
    product_file = f"/etc/products.d/{prodfname}.prod"

    assert auto_container.connection.file(product_file).is_file
    assert auto_container.connection.file(
        "/etc/products.d/baseproduct"
    ).is_symlink
    assert (
        auto_container.connection.file("/etc/products.d/baseproduct").linked_to
        == product_file
    )


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="lifecycle data only available for SLE",
)
def test_lifecycle(auto_container):
    """
    If the container provides lifecycle information, test that we do
    not have unsupported packages installed.
    """

    lifecycle_dir = "/usr/share/lifecycle/data"
    if not auto_container.connection.file(lifecycle_dir).exists:
        return

    assert auto_container.connection.file(f"{lifecycle_dir}/").is_directory

    rpmqpack = auto_container.connection.run_expect(
        [0], "rpm -qa --qf '%{NAME},%{VERSION}\n'"
    ).stdout.splitlines()
    installed_binaries = {}
    for pack in rpmqpack:
        rpm_name, _, rpm_version = pack.partition(",")
        installed_binaries[rpm_name] = rpm_version

    for entry in auto_container.connection.run_expect(
        [0], f"cat {lifecycle_dir}/*.lifecycle"
    ).stdout.splitlines():
        entry = entry.partition("#")[0]
        if not entry.strip() or "," not in entry:
            continue

        entry_name, entry_version, entry_date = entry.split(",")
        if entry_name in installed_binaries:
            if fnmatch.fnmatch(installed_binaries[entry_name], entry_version):
                support_end = datetime.datetime.strptime(
                    entry_date, "%Y-%m-%d"
                )
                assert (
                    datetime.datetime.now() < support_end
                ), f"{entry_name} = {installed_binaries[entry_name]} installed but out of support since {entry_date}"


@pytest.mark.skipif(
    OS_VERSION != "tumbleweed",
    reason="product flavors only available for openSUSE",
)
@pytest.mark.parametrize("container", CONTAINERS_WITH_ZYPPER, indirect=True)
def test_opensuse_product_flavor(container):
    """Checks that this is an appliance-docker flavored product."""
    container.connection.run_expect(
        [0], "rpm -q --whatprovides 'flavor(appliance-docker)'"
    )


@pytest.mark.parametrize(
    "container",
    [c for c in ALL_CONTAINERS if c != BUSYBOX_CONTAINER],
    indirect=True,
)
def test_coreutils_present(container):
    """
    Check that some core utilities (:command:`cat`, :command:`sh`, etc.) exist
    in the container.
    """
    for binary in ("cat", "sh", "bash", "ls", "rm"):
        assert container.connection.exists(binary)


def test_glibc_present(auto_container):
    """ensure that the glibc linker is present"""
    for binary in ("ldconfig", "ldd"):
        assert auto_container.connection.exists(binary)


@pytest.mark.skipif(
    OS_VERSION == "basalt",
    reason="Basalt repos are known to be out of sync with IBS state",
)
@pytest.mark.parametrize(
    "container_per_test", CONTAINERS_WITH_ZYPPER, indirect=True
)
def test_zypper_dup_works(container_per_test: ContainerData) -> None:
    """Check that there are no packages installed that we wouldn't find in SLE
    BCI repo by running :command:`zypper -n dup` and checking that there are no
    conflicts or arch changes and we can update to the state in SLE_BCI repos.
    Then validate that SLE_BCI provides all the packages that are afterwards
    in the container as well except for the known intentional breakages
    (sles-release, skelcd-EULA-bci).
    """
    repo_name = "SLE_BCI"
    if OS_VERSION == "tumbleweed":
        repo_name = "repo-oss"
    if OS_VERSION == "basalt":
        repo_name = "repo-basalt"

    container_per_test.connection.run_expect(
        [0],
        f"timeout 5m zypper -n dup --from {repo_name} -l "
        "--no-allow-vendor-change --no-allow-downgrade --no-allow-arch-change",
    )

    searchresult = ET.fromstring(
        container_per_test.connection.run_expect(
            [0], "zypper -x -n search -t package -v -i '*'"
        ).stdout
    )

    orphaned_packages = {
        child.attrib["name"]
        for child in searchresult.iterfind(
            'search-result/solvable-list/solvable[@repository="(System Packages)"]'
        )
    }

    # kubic-locale-archive should be replaced by glibc-locale-base in the containers
    # but that is a few bytes larger so we accept it as an exception
    known_orphaned_packages = {
        "kubic-locale-archive",
        "skelcd-EULA-bci",
        "sles-release",
        "ALP-dummy-release",
    }

    assert not orphaned_packages.difference(known_orphaned_packages)


@pytest.mark.parametrize(
    "container_per_test", CONTAINERS_WITH_ZYPPER, indirect=True
)
def test_zypper_verify_passes(container_per_test: ContainerData) -> None:
    """Check that there are no packages missing according to zypper verify so that
    users of the container would not get excessive dependencies installed.
    """
    assert (
        "Dependencies of all installed packages are satisfied."
        in container_per_test.connection.run_expect(
            [0], "timeout 5m env LC_ALL=C zypper -n verify -D"
        ).stdout.strip()
    )


@pytest.mark.parametrize(
    "container",
    [
        c
        for c in ALL_CONTAINERS
        if (c not in [INIT_CONTAINER, PCP_CONTAINER] + POSTGRESQL_CONTAINERS)
    ],
    indirect=True,
)
def test_systemd_not_installed_in_all_containers_except_init(container):
    """Ensure that systemd is not present in all containers besides the init
    and pcp containers.

    """
    assert not container.connection.exists("systemctl")

    # we cannot check for an existing package if rpm is not installed
    if container.connection.exists("rpm"):
        assert not container.connection.package("systemd").is_installed


@pytest.mark.parametrize(
    "container",
    ALL_CONTAINERS,
    indirect=True,
)
def test_no_compat_packages(container):
    """Ensure that no host-compatibility packages are installed in the containers"""
    # we cannot check for an existing package if rpm is not installed
    if container.connection.exists("rpm"):
        assert not container.connection.package(
            "compat-usrmerge-tools"
        ).is_installed


@pytest.mark.parametrize("runner", ALL_CONTAINERS)
def test_certificates_are_present(
    host, tmp_path, container_runtime, runner: Container, pytestconfig: Config
):
    """This is a multistage container build, verifying that the certificates are
    correctly set up in the containers.

    In the first step, we build a go binary from
    :py:const:`FETCH_SUSE_DOT_COM` in the golang container. We copy the
    resulting binary into the container under test and execute it in that
    container.

    If the certificates are incorrectly set up, then the GET request will fail.
    """
    multi_stage_build = MultiStageBuild(
        containers={
            "builder": "registry.suse.com/bci/golang:latest",
            "runner": runner,
        },
        containerfile_template=MULTISTAGE_DOCKERFILE,
    )
    multi_stage_build.prepare_build(tmp_path, pytestconfig.rootpath)

    with open(tmp_path / "main.go", "wt", encoding="utf-8") as main_go:
        main_go.write(FETCH_SUSE_DOT_COM)

    # FIXME: ugly duplication of pytest_container internals :-/
    # see: https://github.com/dcermak/pytest_container/issues/149
    iidfile = tmp_path / "iid"
    host.run_expect(
        [0],
        f"{' '.join(container_runtime.build_command + get_extra_build_args(pytestconfig))} "
        f"--iidfile={iidfile} {tmp_path}",
    )
    img_id = container_runtime.get_image_id_from_iidfile(iidfile)

    host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm {' '.join(get_extra_run_args(pytestconfig))} {img_id}",
    )
