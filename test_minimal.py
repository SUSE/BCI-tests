import pytest
from bci_tester.data import MINIMAL_CONTAINER


CONTAINER_IMAGES = [MINIMAL_CONTAINER]

MINIMAL_IMAGE_MAX_SIZE = 40 * 1024 * 1024


@pytest.mark.asyncio
async def test_minimal_image_size(auto_container, container_runtime):
    assert (
        await container_runtime.get_image_size(auto_container.image_url_or_id)
        < MINIMAL_IMAGE_MAX_SIZE
    )


def test_fat_packages_absent(auto_container):
    for pkg in ("zypper", "grep", "diff", "sed", "info", "man"):
        assert not auto_container.connection.exists(pkg)


def test_base_packages_present(auto_container):
    for pkg in ("rpm", "cat", "sh", "bash"):
        assert auto_container.connection.exists(pkg)
