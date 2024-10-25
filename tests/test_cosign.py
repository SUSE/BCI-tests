"""This module contains the tests for the cosign container, the image with cosign pre-installed."""

from bci_tester.data import COSIGN_CONTAINERS

CONTAINER_IMAGES = COSIGN_CONTAINERS


def test_cosign_version(auto_container, host, container_runtime):
    """Test that we can invoke `cosign version` successfully."""

    assert (
        "GitTreeState:  release"
        in host.check_output(
            f"{container_runtime.runner_binary} run --rm {auto_container.image_url_or_id} version"
        ).splitlines()
    )


def test_cosign_verify(auto_container, host, container_runtime):
    """Test that we can invoke `cosign verify` on a bci-container."""
    assert "cosign container image signature" in host.check_output(
        f"{container_runtime.runner_binary} run --rm {auto_container.image_url_or_id} "
        "verify --key https://ftp.suse.com/pub/projects/security/keys/container-key.pem "
        "registry.suse.com/bci/bci-micro:latest"
    )
