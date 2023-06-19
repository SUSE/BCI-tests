"""This module is not really intended to test anything, it mostly is just
present to pull the containers down in one step and not all of them
concurrently. If the environment variable ``BCI_DEVEL_REPO`` has been specified,
then repository will be replaced in the containers and whether this was
successful will be double checked here.

"""
import pytest

from bci_tester.data import BCI_DEVEL_REPO
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import CONTAINERS_WITHOUT_ZYPPER
from bci_tester.util import get_repos_from_connection


@pytest.mark.parametrize(
    "container_per_test", CONTAINERS_WITH_ZYPPER, indirect=True
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

    if suseconnect_injects_repos:
        for _ in range(5):
            if len(repos) > 1:
                break

            repos = get_repos_from_connection(container_per_test.connection)

        assert (
            len(repos) > 1
        ), "On a registered host, we must have more than one repository on the host"
    else:
        # SLE_BCI (optionally SLE_BCI_debug, SLE_BCI_source & MS .Net repo)
        assert len(repos) <= 4
        assert not repo_names - {
            "SLE_BCI",
            "SLE_BCI_debug",
            "SLE_BCI_source",
            "packages-microsoft-com-prod",
        }

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
        "SLE_BCI_debug" in repo_names and "SLE_BCI_source" in repo_names
    ) or (
        "SLE_BCI_debug" not in repo_names
        and "SLE_BCI_source" not in repo_names
    ), "repos SLE_BCI_source and SLE_BCI_debug must either both be present or both missing"

    # check that all enabled repos are valid and can be refreshed
    container_per_test.connection.run_expect([0], "zypper -n ref")


@pytest.mark.parametrize("container", CONTAINERS_WITHOUT_ZYPPER, indirect=True)
def test_container_build(container):
    """Just pull down the minimal and micro containers and ensure that they
    launch.

    """
    container.connection.run_expect([0], "true")
