import xml.etree.ElementTree as ET

import pytest
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BCI_DEVEL_REPO
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER


@pytest.mark.parametrize(
    "container",
    [
        cont
        for cont in ALL_CONTAINERS
        if cont not in (MINIMAL_CONTAINER, MICRO_CONTAINER)
    ],
    indirect=["container"],
)
def test_container_build_and_repo(container, host):
    repos = ET.fromstring(
        container.connection.run_expect([0], "zypper -x repos -u").stdout
    )

    repo_list = [child for child in repos if child.tag == "repo-list"]
    assert len(repo_list) == 1

    # container-suseconnect will inject the correct repositories on registered
    # SLES hosts
    # => if the host is registered, we will have multiple repositories in the
    # container, otherwise we will just have the SLE_BCI repository
    suseconnect_injects_repos: bool = (
        host.system_info.type == "linux"
        and host.system_info.distribution == "sles"
        and host.file("/etc/zypp/credentials.d/SCCcredentials").exists
    )

    if suseconnect_injects_repos:
        assert len(list(repo_list[0])) > 1
    else:
        assert len(list(repo_list[0])) == 1

    sle_bci_repo_candidates = [
        repo for repo in list(repo_list[0]) if repo.get("name") == "SLE_BCI"
    ]
    assert len(sle_bci_repo_candidates) == 1
    sle_bci_repo = sle_bci_repo_candidates[0]

    assert sle_bci_repo.get("name") == "SLE_BCI"
    assert len(list(sle_bci_repo)) == 1

    repo_url = list(sle_bci_repo)[0]
    assert repo_url.text == BCI_DEVEL_REPO

    container.connection.run_expect([0], "zypper -n ref")


@pytest.mark.parametrize(
    "container", [MINIMAL_CONTAINER, MICRO_CONTAINER], indirect=["container"]
)
def test_container_build(container):
    container.connection.run_expect([0], "true")
