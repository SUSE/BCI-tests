"""This module contains general purpose utility functions."""
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict
from typing import List

from pytest_container import Version


def get_host_go_version(host) -> Version:
    # output of go version:
    # go version go1.19.1 linux/amd64
    return Version.parse(
        host.run_expect([0], "go version")
        .stdout.strip()
        .split()[2]
        .replace("go", "")
    )


@dataclass(frozen=True)
class Repository:
    """A class representing a rpm-md repository."""

    alias: str
    name: str
    priority: int
    enabled: bool
    url: str
    gpgcheck: bool
    repo_gpgcheck: bool
    pkg_gpgcheck: bool

    @staticmethod
    def from_xml(repo_element: ET.Element) -> "Repository":
        """Creates a :py:class:`Repository` from the :py:class:`xml.etree.ElementTree`
        element belonging to a single repository element as produced by
        :command:`zypper -x repos`.

        """
        child_elements = list(repo_element)
        assert len(child_elements) == 1
        url = child_elements[0].text
        str_kwargs: Dict[str, str] = {
            k: repo_element.get(k) for k in ("alias", "name")
        }
        bool_kwargs: Dict[str, bool] = {
            k: (repo_element.get(k) == "1")
            for k in ("enabled", "gpgcheck", "repo_gpgcheck", "pkg_gpgcheck")
        }
        return Repository(
            **str_kwargs,
            **bool_kwargs,
            priority=int(repo_element.get("priority")),
            url=url
        )


def get_repos_from_zypper_xmlout(zypper_xmlout: str) -> List[Repository]:
    """Parse the output of :command:`zypper -x repos` and return the list of
    repositories.

    """
    repos = ET.fromstring(zypper_xmlout)
    repo_list = [child for child in repos if child.tag == "repo-list"]
    assert len(repo_list) == 1
    return [Repository.from_xml(repo) for repo in repo_list[0]]


def get_repos_from_connection(con) -> List[Repository]:
    """Gets the list of repositories given a testinfra connection."""
    return get_repos_from_zypper_xmlout(
        con.run_expect([0], "zypper -x repos").stdout
    )
