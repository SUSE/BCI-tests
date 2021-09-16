from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BCI_DEVEL_REPO
from lxml import etree


CONTAINER_IMAGES = ALL_CONTAINERS


def test_container_build_and_repo(auto_container):
    repos = etree.fromstring(
        auto_container.connection.run_expect([0], "zypper -x repos -u").stdout
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
