"""Tests for the SLE_BCI repository itself: can all packages in the repository
be installed and ensure that we do not accidentally ship forbidden packages.

"""

import xml.etree.ElementTree as ET
from typing import Callable
from typing import List

import pytest

from bci_tester.data import ALLOWED_BCI_REPO_OS_VERSIONS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BASE_FIPS_CONTAINERS
from bci_tester.data import BCI_DEVEL_REPO
from bci_tester.data import BCI_REPO_NAME
from bci_tester.data import OS_VERSION
from bci_tester.util import get_repos_from_connection

_RM_ZYPPSERVICE = (
    "rm -v /usr/lib/zypp/plugins/services/container-suseconnect-zypp"
)


def get_package_list(con) -> List[str]:
    """This function returns all packages available from the ``SLE_BCI``
    repository given a container connection.

    """
    zypper_se_xml = ET.fromstring(
        con.check_output("zypper --xmlout se -r SLE_BCI")
    )
    package_list = [
        s.get("name") for s in zypper_se_xml.findall(".//solvable")
    ]
    assert len(package_list) > 3000
    return package_list


def package_name_filter_func(
    packages_to_filter_out: List[str],
) -> Callable[[str], bool]:
    """Returns a function to be used with ``filter`` to remove the strings
    containing any of the strings from `packages_to_filter_out` from an
    iterable.

    """

    def f(pkg_name: str) -> bool:
        for to_filter in packages_to_filter_out:
            if to_filter in pkg_name:
                return False
        return True

    return f


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed", reason="No testing for openSUSE"
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_installcheck(container_per_test):
    """Run installcheck against the SLE_BCI repo + locally installed packages."""
    # Let zypper fetch the repo data and generate solv files.
    container_per_test.connection.check_output("zypper ref")
    container_per_test.connection.check_output("zypper -n in libsolv-tools")
    # Check that all packages in SLE_BCI can be installed, using already installed
    # packages (@System) if necessary. It tries to keep rpm installed
    # but rpm-ndb conflicts with that, so exclude rpm-ndb.
    container_per_test.connection.check_output(
        "installcheck $(uname -m) --exclude 'rpm-ndb' /var/cache/zypp/solv/SLE_BCI/solv --nocheck /var/cache/zypp/solv/@System/solv"
    )


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed", reason="No testing for openSUSE"
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_sle_bci_forbidden_packages(container_per_test):
    """Regression test that no packages containing the following strings are in the
    ``SLE_BCI`` repository:

    - ``kernel``
    - ``yast``
    - ``kvm``
    - ``xen``

    The following packages contain the above strings, but are ok to be shipped:

    - ``system-group-kvm``
    - ``jaxen``
    - ``kernelshark``
    - ``librfxencode0``
    - ``nfs-kernel-server``
    - ``texlive-l3kernel``
    - ``purge-kernels-service``
    - ``"kernel-azure-devel``
    - ``kernel-devel-azure``
    - ``kernel-macros``
    - ``kernel-default-devel``
    - ``kernel-devel``
    - ``kernel-syms``
    - ``kernel-syms-azure``

    """
    package_list = get_package_list(container_per_test.connection)

    ALLOWED_PACKAGES = [
        "system-group-kvm",
        "jaxen",
        "kernelshark",
        "librfxencode0",
        "nfs-kernel-server",
        "texlive-l3kernel",
        "purge-kernels-service",
        "kernel-azure-devel",
        "kernel-devel-azure",
        "kernel-macros",
        "kernel-default-devel",
        "kernel-devel",
        "kernel-syms",
        "kernel-syms-azure",
        # aarch64 only
        "kernel-64kb-devel",
    ]

    FORBIDDEN_PACKAGE_NAMES = ["kernel", "yast", "kvm", "xen"]

    forbidden_packages = list(
        filter(
            package_name_filter_func(ALLOWED_PACKAGES),
            filter(
                lambda p: not package_name_filter_func(
                    FORBIDDEN_PACKAGE_NAMES
                )(p),
                package_list,
            ),
        )
    )

    assert not forbidden_packages, f"package_list must not contain any forbidden packages, but found {', '.join(forbidden_packages)}"


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository - can't test",
)
@pytest.mark.parametrize("pkg", ("git", "curl", "wget", "unzip"))
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_package_installation(container_per_test, pkg):
    """Check that some basic packages (:command:`wget`, :command:`git`,
    :command:`curl` and :command:`unzip`) can be installed.
    We additionally have to remove the ``container-suseconnect`` zypper service
    before running the test to ensure that no SLES repositories are added on
    registered hosts thereby skewing our results.
    """

    container_per_test.connection.check_output(
        f"{_RM_ZYPPSERVICE}; zypper -n in -r {BCI_REPO_NAME} {pkg}"
    )


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository - can't test",
)
@pytest.mark.skipif(
    OS_VERSION == "tumbleweed", reason="No testing for openSUSE"
)
@pytest.mark.parametrize(
    "pkg",
    [
        "libsnmp30",  # bsc#1209442
        "aws-cli",  # disappeared after python311 switch due to unresolvables
        "python3-azure-sdk",  # might also become unresolvable
        "uuidd",  # reported as missing by ironbank user
    ],
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_sle15_packages(container_per_test, pkg):
    """Test that packages that we received reports by users for as missing/broken
    remain installable and available.
    """
    container_per_test.connection.check_output(
        f"{_RM_ZYPPSERVICE}; zypper -n in --dry-run -r {BCI_REPO_NAME} {pkg}"
    )


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository - can't test",
)
@pytest.mark.parametrize(
    "container_per_test",
    [BASE_CONTAINER, *BASE_FIPS_CONTAINERS],
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

        assert (
            len(repos) > 1
        ), "On a registered host, we must have more than one repository on the host"
    else:
        assert len(repos) <= len(expected_repos)
        assert not repo_names - expected_repos

        if OS_VERSION == "tumbleweed":
            for repo_name in "repo-debug", "repo-source":
                container_per_test.connection.run_expect(
                    [0], f"zypper modifyrepo --enable {repo_name}"
                )

    if OS_VERSION != "tumbleweed":
        sle_bci_repo_candidates = [
            repo for repo in repos if repo.name == "SLE_BCI"
        ]
        assert len(sle_bci_repo_candidates) == 1
        sle_bci_repo = sle_bci_repo_candidates[0]

        assert sle_bci_repo.name == "SLE_BCI"
        assert sle_bci_repo.url == BCI_DEVEL_REPO

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
            ("SLE_BCI_debug" in repo_names and "SLE_BCI_source" in repo_names)
            or (
                "SLE_BCI_debug" not in repo_names
                and "SLE_BCI_source" not in repo_names
            )
        ), "repos SLE_BCI_source and SLE_BCI_debug must either both be present or both missing"

    # check that all enabled repos are valid and can be refreshed
    container_per_test.connection.run_expect([0], "zypper -n ref")
