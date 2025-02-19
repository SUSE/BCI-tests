"""Tests for the SLE_BCI repository itself: can all packages in the repository
be installed and ensure that we do not accidentally ship forbidden packages.

"""

import xml.etree.ElementTree as ET
from typing import Callable
from typing import List

import pytest

from bci_tester.data import ALLOWED_BCI_REPO_OS_VERSIONS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BCI_REPO_NAME
from bci_tester.data import OS_VERSION

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

    - ``gcc-build``
    - ``kernel``
    - ``kvm``
    - ``livepatch``
    - ``xen``
    - ``yast``

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

    FORBIDDEN_PACKAGE_NAMES = [
        "gcc-build",
        "libstdc++-build-devel",
        "libgccjit-build-devel",
        "livepatch",
        "kernel",
        "yast",
        "kvm",
        "xen",
    ]

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

    assert not forbidden_packages, (
        f"package_list must not contain any forbidden packages, but found {', '.join(forbidden_packages)}"
    )


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository",
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
    OS_VERSION == "tumbleweed", reason="No testing for openSUSE"
)
@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository - can't test",
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_repo_content_licensing(container_per_test) -> None:
    conn = container_per_test.connection
    conn.check_output("timeout 2m zypper ref && zypper -n in libsolv-tools")

    assert (
        conn.check_output(
            f"set -o pipefail; dumpsolv /var/cache/zypp/solv/{BCI_REPO_NAME}/solv | sed -n '/^solvable:license:.*SUSE-Firmware/p' | wc -l"
        ).strip()
        == "0"
    ), "Found a package with a SUSE-Firmware license"


@pytest.mark.skipif(
    (
        not OS_VERSION.startswith("15")
        or OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS
    ),
    reason="no included BCI repository",
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_codestream_lifecycle(container_per_test):
    """Check that the codestream lifecycle information is available
    and has the expected value."""

    zypper_lifecycle_xml = ET.fromstring(
        container_per_test.connection.check_output(
            "zypper --xmlout -i pd --xmlfwd codestream"
        )
    )
    lifecycle = zypper_lifecycle_xml.find(
        ".//product[@name='SLES']/xmlfwd/codestream/endoflife"
    )
    assert lifecycle is not None, (
        "No endoflife information found in product description"
    )
    assert lifecycle.text == "2031-07-31", (
        f"Expected end of life 2031-07-31, but got {lifecycle.text}"
    )


@pytest.mark.skipif(
    OS_VERSION not in ALLOWED_BCI_REPO_OS_VERSIONS,
    reason="no included BCI repository",
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
        "java-11-openjdk-headless",  # provide java11 until 2026-12-31 see jsc#PED-9926/jsc#NVSHAS-8819
        "libboost_program_options1_66_0",  # bsc#1229894
        "libOpenCL1",  # PED-7838
    ],
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_sle15_packages(container_per_test, pkg):
    """Test that packages that we received reports by users for as missing/broken
    remain installable and available.
    """

    if OS_VERSION not in ("15.6",) and pkg in ("java-11-openjdk-headless",):
        pytest.skip(reason="Only available for SP6")

    container_per_test.connection.check_output(
        f"{_RM_ZYPPSERVICE}; zypper -n in --dry-run -r {BCI_REPO_NAME} {pkg}"
    )
