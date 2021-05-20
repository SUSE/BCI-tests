import os
import socket
from shutil import copy
from time import sleep

import pytest

GRAFANA_PORT = "3000"
GRAFANA_SOCKET = f"tcp://127.0.0.1:{GRAFANA_PORT}"


@pytest.mark.serial
@pytest.mark.parametrize(
    "container_version",
    ["UBI8-Standard", "BCI"],  # ["BCI", "SLE15", "UBI8-Standard"]
)
def test_perf_grafana(host, tmp_path, container_version, container_runtime):
    d = tmp_path / container_version
    d.mkdir()
    copy(
        os.path.join(
            os.path.dirname(__file__),
            "dockerfiles",
            "perftest-grafana",
            container_version,
            "Dockerfile",
        ),
        os.path.join(d, "Dockerfile"),
    )
    cwd = os.getcwd()
    try:
        os.chdir(d)
        cmd = host.run_expect([0], f"""{container_runtime.build_command} -q""")
    finally:
        os.chdir(cwd)

    img_id = str(cmd.stdout).split(":")[-1]

    cmd = host.run_expect(
        [0],
        f"{container_runtime.runner_binary} run --rm -d --name grafana -p {GRAFANA_PORT}:3000 {img_id}",
    )

    try:
        for i in range(12):
            try:
                assert host.socket(GRAFANA_SOCKET).is_listening
            except AssertionError:
                sleep(10)

        assert host.socket(GRAFANA_SOCKET).is_listening
    finally:
        # this could fail if kafka failed to launch
        # (the container would be gone then)
        host.run(
            f"{container_runtime.runner_binary} stop "
            + container_runtime.get_image_id_from_stdout(cmd.stdout)
        )
