"""Tests for the SLE_BCI repository itself: can all packages in the repository
be installed and ensure that we do not accidentally ship forbidden packages.

"""
from typing import Callable
from typing import List

import pytest
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import REPOCLOSURE_CONTAINER


#: Packages that can be installed, but are reported as having dependency issues
#: by :command:`dnf repoclosure`.
#: This is caused by these packages having boolean requires on the kernel, which
#: is not present in the SLE_BCI repository. We check that these packages can be
#: installed in :py:func:`test_package_installation`.
REPOCLOSURE_FALSE_POSITIVES = [
    "multipath-tools",
    "patterns-base-fips",
    "salt-minion",
    "suse-module-tools",
]


def get_package_list(con) -> List[str]:
    package_list = (
        con.run_expect(
            [0],
            "dnf list --available|grep SLE_BCI|awk '{print $1}'",
        )
        .stdout.strip()
        .split("\n")
    )
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


@pytest.mark.parametrize(
    "container_per_test", [REPOCLOSURE_CONTAINER], indirect=True
)
def test_repoclosure(container_per_test):
    """Run :command:`dnf repoclosure` on all packages in the ``SLE_BCI`` repository
    excluding the packages in :py:const`REPOCLOSURE_FALSE_POSITIVES`.

    """
    package_list = filter(
        package_name_filter_func(REPOCLOSURE_FALSE_POSITIVES),
        get_package_list(container_per_test.connection),
    )

    container_per_test.connection.run_expect(
        [0], "dnf repoclosure --pkg " + " --pkg ".join(package_list)
    )


@pytest.mark.parametrize(
    "container_per_test", [REPOCLOSURE_CONTAINER], indirect=True
)
def test_forbidden_packages(container_per_test):
    package_list = get_package_list(container_per_test.connection)

    ALLOWED_PACKAGES = [
        "system-group-kvm.noarch",
        "jaxen.noarch",
        "kernelshark",
        "librfxencode0",
        "nfs-kernel-server",
        "texlive-l3kernel.noarch",
        "purge-kernels-service.noarch",
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
    container_per_test.connection.run_expect([0], f"zypper -n in {pkg}")
