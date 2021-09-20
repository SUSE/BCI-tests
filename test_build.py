import pytest
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BCI_DEVEL_REPO
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from lxml import etree


@pytest.mark.parametrize(
    "container",
    [
        cont
        for cont in ALL_CONTAINERS
        if cont not in (MINIMAL_CONTAINER, MICRO_CONTAINER)
    ],
    indirect=["container"],
)
def test_container_build_and_repo(container):
    repos = etree.fromstring(
        container.connection.run_expect([0], "zypper -x repos -u").stdout
    )

    repos_list = repos.xpath("//repo-list")
    assert len(repos_list) == 1
    assert len(repos_list[0].getchildren()) == 1

    sle_bci_repo = repos_list[0].getchildren()[0]
    assert sle_bci_repo.get("alias") == "SLE_BCI"
    assert sle_bci_repo.get("name") == "SLE_BCI"
    assert len(sle_bci_repo.getchildren()) == 1

    repo_url = sle_bci_repo.getchildren()[0]
    assert repo_url.text == BCI_DEVEL_REPO


@pytest.mark.parametrize(
    "container", [MINIMAL_CONTAINER, MICRO_CONTAINER], indirect=["container"]
)
def test_container_build(container):
    container.connection.run_expect([0], "true")
