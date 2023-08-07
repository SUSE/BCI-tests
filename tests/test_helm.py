"""This module contains the tests for the helm container, the image with helm pre-installed.
"""
from bci_tester.data import HELM_CONTAINER


CONTAINER_IMAGES = (HELM_CONTAINER,)


def test_helm_version(auto_container, host, container_runtime):
    assert (
        "GitTreeState"
        in host.run_expect(
            [0],
            f"{container_runtime.runner_binary} run --rm {auto_container.image_url_or_id} version",
        ).stdout.strip()
    )
