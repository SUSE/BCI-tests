# If we estimate that tests should also contain the time to fetch the image,
# create a new tox.ini unit, copying the base testcommands, remove the cli for fetching the containers.
# Alternatively, use the containers data and check their size on docker.
import os
from textwrap import dedent
from shutil import copytree
from time import sleep


import pytest


KAFKA_ADDRESS = "localhost:19092"
KAFKA_SOCKET = "tcp://127.0.0.1:{KAFKA_ADDRESS.split(':')[-1]}"


@pytest.fixture(scope="function")
def zookeeper(host, container_runtime):
    """Fixture to launch zookeeper based on the docker compose file from
    confluent.

    See:
    https://github.com/confluentinc/kafka-images/blob/master/examples/confluent-server/docker-compose.yml
    """
    cmd = host.run_expect(
        [0],
        dedent(
            f"""{container_runtime.runner_binary} run --network=host -d \
                -e ZOOKEEPER_CLIENT_PORT=22181 \
                --add-host=moby:127.0.0.1 \
                confluentinc/cp-zookeeper:latest
            """
        ),
    )
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)
    yield img_id

    host.run_expect([0], f"{container_runtime.runner_binary} rm -f {img_id}")


@pytest.mark.serial
@pytest.mark.parametrize(
    "container_version", ["UBI8-Standard"]  # ["BCI", "SLE15", "UBI8-Standard"]
)
def test_perf_kafka(
    host, tmp_path, container_version, container_runtime, zookeeper
):
    d = tmp_path / container_version
    buildtree = copytree(
        os.path.join(
            os.path.dirname(__file__),
            "dockerfiles",
            "perftest-kafka",
            container_version,
        ),
        d,
    )
    cwd = os.getcwd()
    try:
        os.chdir(buildtree)
        cmd = host.run_expect(
            [0],
            dedent(
                f"""{container_runtime.build_command} -q \
                --build-arg DOCKER_UPSTREAM_REGISTRY=docker.io/ \
                --build-arg PROJECT_VERSION=2.8.0 \
                --build-arg GIT_COMMIT=ebb1d6e21cc9213071ee1c6a15ec3411fc215b810 \
                --build-arg ARTIFACT_ID=kafka \
                --build-arg CONFLUENT_VERSION=6.0.0 \
                --build-arg CONFLUENT_PACKAGES_REPO=http://packages.confluent.io/rpm/6.0 \
                --build-arg CONFLUENT_PLATFORM_LABEL=foo \
                --build-arg KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://{KAFKA_ADDRESS}" \
                --build-arg KAFKA_ZOOKEEPER_CONNECT="localhost:22181"
            """
            ),
        )
    finally:
        os.chdir(cwd)

    img_id = str(cmd.stdout).split(":")[-1]

    cmd = host.run_expect(
        [0],
        dedent(
            f"""{container_runtime.runner_binary} run \
                --rm -d --network=host \
                --add-host=moby:127.0.0.1 \
                -e KAFKA_ZOOKEEPER_CONNECT="localhost:22181" \
                -e KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://{KAFKA_ADDRESS}" \
                {img_id}
        """
        ),
    )

    try:
        for i in range(12):
            try:
                assert host.socket(KAFKA_SOCKET).is_listening
            except AssertionError:
                sleep(10)

        assert host.socket(KAFKA_SOCKET).is_listening
    finally:
        # this could fail if kafka failed to launch
        # (the container would be gone then)
        host.run(
            f"{container_runtime.runner_binary} stop "
            + container_runtime.get_image_id_from_stdout(cmd.stdout)
        )
