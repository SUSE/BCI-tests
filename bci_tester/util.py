"""This module contains general purpose utility functions."""

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional

from pytest_container import Version


def get_host_go_version(host) -> Version:
    """Return the Version of the host installed go compiler."""
    # output of go version:
    # go version go1.19.1 linux/amd64
    return Version.parse(
        host.check_output("go version").split()[2].replace("go", "")
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
            url=url,
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
    return get_repos_from_zypper_xmlout(con.check_output("zypper -x repos"))


def get_spr_version(os_version: Optional[str] = None) -> Optional[str]:
    """Return the SPR version string for the given OS_VERSION, or None if not an SPR variant."""
    if os_version is None:
        os_version = os.getenv("OS_VERSION", "15.7")
    match = re.search(
        r"(\d+\.\d+)-spr(\d+\.\d+){0,1}", os_version
    )  # 15.6-spr, 15.7-spr, 15.7-spr1.2, etc.
    if match is None:
        return None

    if match[2]:
        return match[2]

    if match[1] == "15.6":
        return "1.0"

    if match[1] == "15.7":
        return "1.1"

    return None


def get_spr_namespace(os_version: Optional[str] = None) -> str:
    """Return the registry namespace suffix for SPR (e.g. '/1.2') or empty string."""
    spr_ver = get_spr_version(os_version)
    return "" if spr_ver in (None, "1.0", "1.1") else f"/{spr_ver}"


def is_spr(os_version: Optional[str] = None) -> bool:
    """Return True if the given OS_VERSION is an SPR variant."""
    return get_spr_version(os_version) is not None


def get_repository_name(image_type: str) -> str:
    """Return the registry path segment for the given image type and current TARGET/OS_VERSION."""
    target = os.getenv("TARGET", "obs")
    os_version = os.getenv("OS_VERSION", "15.7")
    if target in ("dso", "ibs-released"):
        return ""
    if target == "ibs-cr":
        if os_version == "16.0-pc2025":
            return "containers_registry_16.0/"
        return "containerfile/" if os_version.startswith("16") else "images/"
    if target in ("factory-totest", "factory-arm-totest"):
        return "containers/"
    if image_type == "dockerfile":
        return "containerfile/"
    if image_type == "kiwi":
        return "containerkiwi/" if os_version.startswith("16") else "images/"
    raise AssertionError(f"invalid image_type: {image_type}")
