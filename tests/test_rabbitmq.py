"""This module contains the tests for the rabbitmq container."""

from pytest_container.container import ContainerData

from bci_tester.data import RABBITMQ_CONTAINER

CONTAINER_IMAGES = [RABBITMQ_CONTAINER]


def test_rabbitmq_version(auto_container: ContainerData):
    """Test that rabbitmq version can be detected."""

    rabbitmq_version = auto_container.connection.check_output(
        "rabbitmqctl version"
    )

    assert rabbitmq_version.startswith("4.")
