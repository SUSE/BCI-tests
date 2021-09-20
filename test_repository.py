import pytest
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import REPOCLOSURE_CONTAINER


@pytest.mark.parametrize(
    "container", [REPOCLOSURE_CONTAINER], indirect=["container"]
)
def test_repoclosure(container):
    # workaround for suse-module-tools requiring '(kmod(sg.ko) if kernel)' which
    # repoclosure interprets as an issue, because 'kernel' could be present on
    # the system, but it is not available in the repository
    package_list = (
        container.connection.run_expect(
            [0],
            "dnf list --available|grep SLE_BCI|awk '{print $1}'|sed '/suse-module-tools/d'",
        )
        .stdout.strip()
        .split("\n")
    )

    # sanity checks
    assert (
        len(package_list) > 100
    ), "just a sanity check that we have a few packages in the list"
    assert not [
        pkg for pkg in package_list if "suse-module-tools" in pkg
    ], "suse-module-tools must not be present in package_list"

    # actual checks
    assert not [
        pkg for pkg in package_list if "kernel" in pkg
    ], "package_list must not contain any kernel packages"

    container.connection.run_expect(
        [0], "dnf repoclosure --pkg " + " --pkg ".join(package_list)
    )


@pytest.mark.parametrize("pkg", ["git", "curl", "wget", "unzip"])
@pytest.mark.parametrize("container", [BASE_CONTAINER], indirect=["container"])
def test_package_installation(container, pkg):
    container.connection.run_expect([0], f"zypper -n in {pkg}")
