"""
This module contains tests that are run for **all** containers.
"""

import datetime
import fnmatch
import json
import pathlib
import xml.etree.ElementTree as ET

import packaging.version
import pytest
from _pytest.config import Config
from pytest_container import Container
from pytest_container import DerivedContainer
from pytest_container import MultiStageBuild
from pytest_container import get_extra_build_args
from pytest_container import get_extra_run_args
from pytest_container.container import BindMount
from pytest_container.container import ContainerData

from bci_tester.data import ALLOWED_BCI_REPO_OS_VERSIONS
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BCI_DEVEL_REPO
from bci_tester.data import BCI_REPO_NAME
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINERS_WITHOUT_ZYPPER
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import CONTAINERS_WITH_ZYPPER_AS_ROOT
from bci_tester.data import DISTRIBUTION_CONTAINER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import KIWI_CONTAINERS
from bci_tester.data import LTSS_BASE_CONTAINERS
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import OS_PRETTY_NAME
from bci_tester.data import OS_VERSION
from bci_tester.data import OS_VERSION_ID
from bci_tester.data import PCP_CONTAINERS
from bci_tester.data import RELEASED_SLE_VERSIONS
from bci_tester.util import get_repos_from_connection

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
RUN CGO_ENABLED=0 GOOS=linux go build main.go

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
                        auto_container.connection.check_output(
                            f". /etc/os-release && echo ${var_name}"
                        ),
                        "%Y%m%d",
                    )
                ).days < 10
                continue

        # Ignore the Milestone suffix in the form of "SUSE Linux Enterprise Server XX YY (AlphaZ)"
        assert (
            auto_container.connection.check_output(
                f". /etc/os-release && echo ${var_name}"
            )
            .partition("(")[0]
            .strip()
            == expected_value
        )


@pytest.mark.skipif(
    OS_VERSION in ("15.3", "15.4", "15.5", "basalt"),
    reason="branding packages are known to not be installed",
)
@pytest.mark.parametrize(
    "container",
    CONTAINERS_WITH_ZYPPER,
    indirect=True,
)
def test_branding(container):
    """
    check that the :file:`/etc/SUSE-brand` file exists and containers SLE branding
    """
    location = "/etc/SUSE-brand"
    branding = "SLE"
    if OS_VERSION == "tumbleweed":
        branding = "openSUSE"
    if OS_VERSION in ("basalt", "tumbleweed"):
        location = "/usr/etc/SUSE-brand"
    assert container.connection.file(location).exists
    assert branding in container.connection.file(location).content_string


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

    rpmqpack = auto_container.connection.check_output(
        "rpm -qa --qf '%{NAME},%{VERSION}\n'"
    ).splitlines()
    installed_binaries = {}
    for pack in rpmqpack:
        rpm_name, _, rpm_version = pack.partition(",")
        installed_binaries[rpm_name] = rpm_version

    for entry in auto_container.connection.check_output(
        f"cat {lifecycle_dir}/*.lifecycle"
    ).splitlines():
        entry = entry.partition("#")[0]
        if not entry.strip() or "," not in entry:
            continue

        entry_name, entry_version, entry_date = entry.split(",")
        if entry_name in installed_binaries:
            if fnmatch.fnmatch(installed_binaries[entry_name], entry_version):
                support_end = datetime.datetime.strptime(
                    entry_date, "%Y-%m-%d"
                )
                assert datetime.datetime.now() < support_end, (
                    f"{entry_name} = {installed_binaries[entry_name]} installed but out of support since {entry_date}"
                )


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
    [
        c
        for c in ALL_CONTAINERS
        if c not in (BUSYBOX_CONTAINER, DISTRIBUTION_CONTAINER)
    ],
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


# this is all containers with zypper but with a temporary directory bind mounted
# into /solv/, so that we can share the output of `dumpsolv -j` directly with
# the host instead of passing it on via stdout which pollutes the logs making
# them unreadable
_CONTAINERS_WITH_VOLUME_MOUNT = []
for ctr in CONTAINERS_WITH_ZYPPER_AS_ROOT:
    new_vol_mounts = (ctr.volume_mounts or []) + [BindMount("/solv/")]
    kwargs = {**ctr.dict()}
    kwargs.pop("volume_mounts")
    _CONTAINERS_WITH_VOLUME_MOUNT.append(
        DerivedContainer(volume_mounts=new_vol_mounts, **kwargs),
    )


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="LTSS containers are known to be non-functional with BCI_repo ",
)
@pytest.mark.parametrize(
    "container", _CONTAINERS_WITH_VOLUME_MOUNT, indirect=True
)
def test_no_downgrade_on_install(container: ContainerData) -> None:
    """Check that we can install any additional package in the container.

    Check that installing any additional package would not cause a downgrade
    of any package already installed in the container as that would throw
    a question to the user and break the builds.
    """

    conn = container.connection
    conn.run_expect([0], "timeout 2m zypper ref && zypper -n in libsolv-tools")

    conn.check_output(
        "dumpsolv -j /var/cache/zypp/solv/@System/solv > /solv/system"
    )
    conn.check_output(
        f"dumpsolv -j /var/cache/zypp/solv/{BCI_REPO_NAME}/solv > /solv/bci"
    )

    # sanity check
    assert container.container.volume_mounts
    solv_mount = container.container.volume_mounts[-1]
    assert isinstance(solv_mount, BindMount) and solv_mount.host_path

    solv_path = pathlib.Path(solv_mount.host_path)
    with open(solv_path / "system", "r", encoding="utf8") as system_solv_f:
        system_solv = json.load(system_solv_f)
    with open(solv_path / "bci", "r", encoding="utf8") as bci_solv_f:
        bci_solv = json.load(bci_solv_f)

    installed_pkgs = {
        solvable["solvable:name"]: solvable["solvable:evr"]
        for solvable in system_solv["repositories"][0]["solvables"]
    }
    bci_pkgs = {}
    for solvable in bci_solv["repositories"][0]["solvables"]:
        bci_pkgs[solvable["solvable:name"]] = solvable["solvable:evr"]
        if solvable["solvable:name"] in installed_pkgs:
            continue
        for req in solvable.get("solvable:requires", ()):
            # Skip boolean dependencies or unversioned ones
            if "(" in req or " = " not in req:
                continue
            name, _, version = req.partition(" = ")
            if name in installed_pkgs:
                installed_version, _, installed_release = installed_pkgs[
                    name
                ].partition("-")
                version, _, release = version.partition("-")
                if installed_version == version and release:
                    assert packaging.version.parse(
                        installed_release
                    ) <= packaging.version.parse(release), (
                        f"Installed {name} = {installed_release} is newer than "
                        f"what {solvable['solvable:name']} requires (= {release})"
                    )


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="LTSS containers are known to be non-functional with BCI_repo ",
)
@pytest.mark.skipif(
    OS_VERSION == "15.6-ai",
    reason="AI containers include unpublished packages",
)
@pytest.mark.parametrize(
    "container_per_test",
    [
        c
        for c in CONTAINERS_WITH_ZYPPER_AS_ROOT
        if c not in LTSS_BASE_CONTAINERS
    ],
    indirect=True,
)
def test_no_orphaned_packages(container_per_test: ContainerData) -> None:
    """Check that containers do not contain any package that isn't also
    available via repositories.
    """

    container_per_test.connection.check_output(
        f"timeout 5m zypper -n dup --from {BCI_REPO_NAME} -l "
        "--no-allow-vendor-change --no-allow-name-change --no-allow-arch-change "
        "--allow-downgrade"
    )

    searchresult = ET.fromstring(
        container_per_test.connection.check_output(
            "zypper -x -n search -t package -v -i '*'"
        )
    )

    orphaned_packages = {
        child.attrib["name"]
        for child in searchresult.iterfind(
            'search-result/solvable-list/solvable[@repository="(System Packages)"]'
        )
    }

    monitoring_stack_packages = {
        "prometheus",
        "alertmanager",
        "blackbox_exporter",
        "grafana",
        "system-user-grafana",
        "golang-github-prometheus-alertmanager",
        "golang-github-prometheus-prometheus",
        "system-user-prometheus",
        "prometheus-blackbox_exporter",
    }

    python39_stack_packages = {
        "libpython3_9-1_0",
        "python39",
        "python39-base",
        "python39-devel",
        "python39-pip",
        "python39-setuptools",
    }

    # kubic-locale-archive should be replaced by glibc-locale-base in the containers
    # but that is a few bytes larger so we accept it as an exception
    known_orphaned_packages = {
        "kubic-locale-archive",
        "skelcd-EULA-bci",
        "sles-ltss-release",
        "sles-release",
        "ALP-dummy-release",
        "sle-module-basesystem-release",
        "sle-module-python3-release",
        "sle-module-server-applications-release",
    }.union(monitoring_stack_packages).union(python39_stack_packages)
    assert not orphaned_packages.difference(known_orphaned_packages)


@pytest.mark.parametrize(
    "container", CONTAINERS_WITH_ZYPPER_AS_ROOT, indirect=True
)
def test_zypper_verify_passes(container: ContainerData) -> None:
    """Check that there are no packages missing according to zypper verify so that
    users of the container would not get excessive dependencies installed.
    """
    assert (
        "Dependencies of all installed packages are satisfied."
        in container.connection.check_output(
            "timeout 5m env LC_ALL=C zypper --no-refresh -n verify -D"
        )
    )


@pytest.mark.parametrize("container", CONTAINERS_WITHOUT_ZYPPER, indirect=True)
def test_zypper_not_present_in_containers_without_it(
    container: ContainerData,
) -> None:
    """Sanity check that containers which are expected to not contain zypper,
    actually do not contain it.

    """
    container.connection.run_expect([1, 127], "command -v zypper")


# PCP_CONTAINERS: uses systemd for starting multiple services
# KIWI_CONTAINERS: pulls lvm2 which pulls systemd
@pytest.mark.parametrize(
    "container",
    [
        c
        for c in ALL_CONTAINERS
        if (
            c
            not in PCP_CONTAINERS
            + [INIT_CONTAINER]
            + KIWI_CONTAINERS
            + ([KERNEL_MODULE_CONTAINER] if OS_VERSION == "16.0" else [])
        )
    ],
    indirect=True,
)
def test_systemd_not_installed_in_all_containers_except_init(container):
    """Ensure that systemd is not present in all containers besides the init
    pcp, and postfix containers.

    """
    assert not container.connection.exists("systemctl")

    # we cannot check for an existing package if rpm is not installed
    if container.connection.exists("rpm"):
        assert not container.connection.package("systemd").is_installed, (
            "systemd is installed in this container!"
        )


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


@pytest.mark.parametrize(
    "container",
    [c for c in ALL_CONTAINERS if c not in LTSS_BASE_CONTAINERS],
    indirect=True,
)
def test_bci_eula_is_correctly_available(container: ContainerData) -> None:
    """Ensure that the BCI EULA exists iff it's not a LTSS container"""

    bci_license = "/usr/share/licenses/product/BCI/license.txt"
    if (
        OS_VERSION in ALLOWED_BCI_REPO_OS_VERSIONS
        and OS_VERSION in RELEASED_SLE_VERSIONS
    ):
        assert container.connection.file(bci_license).exists, (
            "BCI EULA is missing"
        )
        assert (
            "SUSE Linux Enterprise Base Container Image License"
            in container.connection.check_output(f"head -n 1 {bci_license}")
        ), "EULA is not the expected BCI EULA"
        return

    # LTSS containers should not have the BCI license, however we currently
    # are running tests for the bci-* base os containers which are not LTSS
    # and still contain a BCI license. As they are out of maintenance, we
    # need to ignore them
    if OS_VERSION in RELEASED_SLE_VERSIONS:
        if container.container in (
            BASE_CONTAINER.values[0],
            INIT_CONTAINER.values[0],
            MINIMAL_CONTAINER.values[0],
            MICRO_CONTAINER.values[0],
        ):
            pytest.skip("Unmaintained bci-* base os containers are not tested")

        assert not container.connection.file(bci_license).exists, (
            "BCI EULA shall not be in LTSS container"
        )


@pytest.mark.skipif(
    OS_VERSION in RELEASED_SLE_VERSIONS or OS_VERSION in ("tumbleweed",),
    reason="BETA EULA not expected",
)
@pytest.mark.parametrize(
    "container",
    ALL_CONTAINERS,
    indirect=True,
)
def test_sles_beta_eula_exists(container):
    """Ensure that the SLES Beta eula exists in the container"""

    assert (
        "SUSE(R) End User License Agreement for Beta Software"
        in container.connection.check_output(
            "head -n 1 /usr/share/licenses/product/base/license.txt"
        )
    )


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
    multi_stage_build.prepare_build(
        tmp_path, container_runtime, pytestconfig.rootpath
    )

    with open(tmp_path / "main.go", "w", encoding="utf-8") as main_go:
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


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository - can't test",
)
@pytest.mark.parametrize(
    "container_per_test",
    [
        c
        for c in CONTAINERS_WITH_ZYPPER_AS_ROOT
        if c not in LTSS_BASE_CONTAINERS
    ],
    indirect=True,
)
def test_container_build_and_repo(container_per_test, host):
    """Test all containers with zypper in them whether at least the ``SLE_BCI``
    repository is present (if the host is unregistered). If a custom value for
    the repository url has been supplied, then check that it is correct.

    If the host is registered, then we check that there are more than one
    repository present.

    Additionally, check if the ``SLE_BCI_debug`` and ``SLE_BCI_source`` repos
    are either both present or both absent. If both are present, enable them to
    check that the URIs are valid.

    """
    # container-suseconnect will inject the correct repositories on registered
    # SLES hosts
    # => if the host is registered, we will have multiple repositories in the
    # container, otherwise we will just have the SLE_BCI repository
    suseconnect_injects_repos: bool = (
        host.system_info.type == "linux"
        and host.system_info.distribution == "sles"
        and host.file("/etc/zypp/credentials.d/SCCcredentials").exists
    )

    repos = get_repos_from_connection(container_per_test.connection)
    repo_names = {repo.name for repo in repos}

    expected_repos = (
        {
            "openSUSE-Tumbleweed-Debug",
            "openSUSE-Tumbleweed-Non-Oss",
            "openSUSE-Tumbleweed-Oss",
            "openSUSE-Tumbleweed-Source",
            "openSUSE-Tumbleweed-Update",
            "Open H.264 Codec (openSUSE Tumbleweed)",
        }
        if OS_VERSION == "tumbleweed"
        else {
            "SLE_BCI",
            "SLE_BCI_debug",
            "SLE_BCI_source",
            "packages-microsoft-com-prod",
        }
    )

    if suseconnect_injects_repos:
        for _ in range(5):
            if len(repos) > 1:
                break

            repos = get_repos_from_connection(container_per_test.connection)

        assert len(repos) > 1, (
            "On a registered host, we must have more than one repository on the host"
        )
    else:
        assert len(repos) <= len(expected_repos)
        assert not repo_names - expected_repos

        if OS_VERSION == "tumbleweed":
            for repo_name in "repo-debug", "repo-source":
                container_per_test.connection.run_expect(
                    [0], f"zypper modifyrepo --enable {repo_name}"
                )

    sle_bci_repo_candidates = [
        repo
        for repo in repos
        if repo.name in ("SLE_BCI", "openSUSE-Tumbleweed-Oss")
    ]
    assert len(sle_bci_repo_candidates) == 1
    sle_bci_repo = sle_bci_repo_candidates[0]
    assert sle_bci_repo.url == BCI_DEVEL_REPO

    if OS_VERSION != "tumbleweed":
        assert sle_bci_repo.name == "SLE_BCI"

        # find the debug and source repositories in the repo list, enable them so
        # that we will check their url in the zypper ref call at the end
        for repo_name in "SLE_BCI_debug", "SLE_BCI_source":
            candidates = [repo for repo in repos if repo.name == repo_name]
            assert len(candidates) in (0, 1)

            if candidates:
                container_per_test.connection.run_expect(
                    [0], f"zypper modifyrepo --enable {candidates[0].alias}"
                )

        assert (
            "SLE_BCI_debug" in repo_names and "SLE_BCI_source" in repo_names
        ) or (
            "SLE_BCI_debug" not in repo_names
            and "SLE_BCI_source" not in repo_names
        ), (
            "repos SLE_BCI_source and SLE_BCI_debug must either both be present or both missing"
        )

    # check that all enabled repos are valid and can be refreshed
    container_per_test.connection.run_expect([0], "zypper -n ref")
