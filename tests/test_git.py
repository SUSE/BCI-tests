"""This module contains the tests for the git container, the image with git pre-installed.
"""
from bci_tester.data import GIT_CONTAINER


CONTAINER_IMAGES = (GIT_CONTAINER,)


def test_git_version(auto_container, host):
    assert (
        "git version 2."
        in auto_container.connection.run_expect(
            [0], "git --version"
        ).stdout.strip()
    )
