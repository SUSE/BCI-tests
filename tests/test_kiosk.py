"""This module contains the tests for the Kiosk xorg client container."""

import pytest
from _pytest.config import Config
from pytest_container import MultiStageBuild

from bci_tester.data import KIOSK_XORG_CLIENT_CONTAINERS

CONTAINER_IMAGES = (KIOSK_XORG_CLIENT_CONTAINERS,)

ELECTRON_APP_BUILD = """
FROM $runner as target
FROM $builder as builder
WORKDIR /src
RUN npm install --omit=dev electron@44.2.0
RUN node_modules/.bin/install-electron

FROM target
COPY --from=builder /src/node_modules/electron/dist /usr/local/electron
USER user
RUN test "$$(/usr/local/electron/electron -v 2>/dev/null)" = "v44.2.0"
"""


@pytest.mark.parametrize(
    "container_per_test",
    KIOSK_XORG_CLIENT_CONTAINERS,
    indirect=True,
)
def test_kiosk_electron(
    container_per_test, tmp_path, container_runtime, pytestconfig: Config
):
    """Test that we can build an electron container."""

    multi_stage_build = MultiStageBuild(
        containers={
            "builder": "registry.suse.com/bci/node:24",
            "runner": container_per_test.container,
        },
        containerfile_template=ELECTRON_APP_BUILD,
    )
    multi_stage_build.prepare_build(
        tmp_path, container_runtime, pytestconfig.rootpath
    )
