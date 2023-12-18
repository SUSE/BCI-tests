"""Tests for the SLE_BCI repository itself: can all packages in the repository
be installed and ensure that we do not accidentally ship forbidden packages.

"""
from typing import Callable
from typing import List

import pytest
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BCI_REPO_NAME
from bci_tester.data import OS_SP_VERSION
from bci_tester.data import OS_VERSION
from bci_tester.data import REPOCLOSURE_CONTAINER


_RM_ZYPPSERVICE = (
    "rm -v /usr/lib/zypp/plugins/services/container-suseconnect-zypp"
)

#: Packages that can be installed, but are reported as having dependency issues
#: by :command:`dnf repoclosure`.
#: This is caused by these packages having boolean requires on the kernel, which
#: is not present in the SLE_BCI repository. We check that these packages can be
#: installed in :py:func:`test_package_installation`.
REPOCLOSURE_FALSE_POSITIVES = (
    [
        "multipath-tools",
        "patterns-base-fips",
        "patterns-base-minimal_base",
        "podman",
        "salt-minion",
        "suse-module-tools",
        "typelib-1_0-Gtk-3_0",
    ]
    + (
        [
            "qml-autoreqprov",
            "typelib-1_0-Gtk-4_0",
            "python311-aiohttp",
            "python311-libcst",
            "kernel-default-devel",
        ]
        if OS_SP_VERSION >= 4
        else []
    )
    + (
        ["open-vm-tools"]
        if OS_SP_VERSION >= 5
        and LOCALHOST.system_info.arch in ("aarch64", "x86_64")
        else []
    )
    + (
        ["open-vm-tools"]
        if OS_SP_VERSION in (3, 4) and LOCALHOST.system_info.arch in ("x86_64")
        else []
    )
)

#: Packages that have broken dependencies by intention and should be excluded
#: from the repoclosure checks
KNOWN_BROKEN = [
    #: aaa_base and kernel-rt_debug require 'distribution-release', which is
    #: provided by `sles-release`.
    #: However, `sles-release` is not in the repository, as we do not want
    #: people to be able to build their own SLES from the SLE_BCI repo alone.
    "aaa_base",
]


def get_package_list(con) -> List[str]:
    """This function returns all packages available from the ``SLE_BCI`` repository
    given a container connection.

    """
    package_list = con.check_output(
        f"dnf list --available|grep -F '{BCI_REPO_NAME}' | cut -d' ' -f1",
    ).splitlines()
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
@pytest.mark.parametrize(
    "container_per_test", [REPOCLOSURE_CONTAINER], indirect=True
)
def test_repoclosure(container_per_test):
    """Run :command:`dnf repoclosure` on all packages in the ``SLE_BCI`` repository
    excluding the packages in :py:const`REPOCLOSURE_FALSE_POSITIVES`.

    """
    package_list = list(
        filter(
            package_name_filter_func(
                REPOCLOSURE_FALSE_POSITIVES + KNOWN_BROKEN
            ),
            get_package_list(container_per_test.connection),
        )
    )

    for i in range(len(package_list) // 500):
        container_per_test.connection.run_expect(
            [0],
            "dnf repoclosure --pkg "
            + " --pkg ".join(package_list[i * 500 : (i + 1) * 500]),
        )


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed", reason="No testing for openSUSE"
)
@pytest.mark.parametrize(
    "container_per_test", [REPOCLOSURE_CONTAINER], indirect=True
)
def test_sle_bci_forbidden_packages(container_per_test):
    """Regression test that no packages containing the following strings are in the
    ``SLE_BCI`` repository:

    - ``kernel``
    - ``yast``
    - ``kvm``
    - ``xen``

    The following packages contain the above strings, but are ok to be shipped:

    - ``system-group-kvm.noarch``
    - ``jaxen.noarch``
    - ``kernelshark``
    - ``librfxencode0``
    - ``nfs-kernel-server``
    - ``texlive-l3kernel.noarch``
    - ``purge-kernels-service.noarch``

    """
    package_list = get_package_list(container_per_test.connection)

    ALLOWED_PACKAGES = [
        "system-group-kvm.noarch",
        "jaxen.noarch",
        "kernelshark",
        "librfxencode0",
        "nfs-kernel-server",
        "texlive-l3kernel.noarch",
        "purge-kernels-service.noarch",
        f"kernel-azure-devel.{LOCALHOST.system_info.arch}",
        "kernel-devel-azure.noarch",
        "kernel-macros.noarch",
        f"kernel-default-devel.{LOCALHOST.system_info.arch}",
        "kernel-devel.noarch",
        f"kernel-syms.{LOCALHOST.system_info.arch}",
        f"kernel-syms-azure.{LOCALHOST.system_info.arch}",
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

    assert (
        not forbidden_packages
    ), f"package_list must not contain any forbidden packages, but found {', '.join(forbidden_packages)}"


@pytest.mark.parametrize(
    "pkg", ["git", "curl", "wget", "unzip"] + REPOCLOSURE_FALSE_POSITIVES
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_package_installation(container_per_test, pkg):
    """Check that some basic packages (:command:`wget`, :command:`git`,
    :command:`curl` and :command:`unzip`) can be installed. Additionally, try to
    install all packages from :py:const:`REPOCLOSURE_FALSE_POSITIVES`, ensuring
    that they are not accidentally not installable.
    We additionally have to remove the ``container-suseconnect`` zypper service before running the test to ensure that no SLES repositories are added on registered hosts thereby skewing our results.
    """

    container_per_test.connection.check_output(
        f"{_RM_ZYPPSERVICE}; zypper -n in -r {BCI_REPO_NAME} {pkg}"
    )


@pytest.mark.skipif(
    OS_VERSION == "tumbleweed", reason="No testing for openSUSE"
)
@pytest.mark.parametrize(
    "pkg",
    [
        "libsnmp30",  # bsc#1209442
    ],
)
@pytest.mark.parametrize("container_per_test", [BASE_CONTAINER], indirect=True)
def test_sle15_packages(container_per_test, pkg):
    """Test that packages that we received reports by users for as missing/broken
    remain installable and available.
    """
    container_per_test.connection.check_output(
        f"{_RM_ZYPPSERVICE}; zypper -n in -r {BCI_REPO_NAME} {pkg}"
    )
