"""This module contains the tests for the gemini-cli container."""

import os
import tempfile
from pathlib import Path

import pytest

from bci_tester.data import GEMINI_CONTAINER
from bci_tester.runtime_choice import PODMAN_SELECTED

CONTAINER_IMAGES = (GEMINI_CONTAINER,)


@pytest.mark.skipif(not PODMAN_SELECTED, reason="PODMAN required")
def test_gemini_version(auto_container, host, container_runtime):
    """Test that we can invoke `gemini version` successfully."""

    # setup an empty
    with tempfile.TemporaryDirectory() as test_home:
        gemini_dir = Path(test_home) / ".gemini"
        gemini_dir.mkdir()

        assert host.check_output(
            f"{container_runtime.runner_binary} container runlabel run {auto_container.image_url_or_id} -- --version",
            env=os.environ | {"HOME": test_home},
        ).startswith("0")
