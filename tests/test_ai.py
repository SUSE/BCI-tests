"""This module contains the tests for the SUSE AI container."""

import pytest
import requests
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import MILVUS_CONTAINER
from bci_tester.data import OLLAMA_CONTAINER
from bci_tester.data import OPENWEBUI_CONTAINER
from bci_tester.data import PYTORCH_CONTAINER

CONTAINER_IMAGES = (
    OLLAMA_CONTAINER,
    OPENWEBUI_CONTAINER,
    MILVUS_CONTAINER,
    PYTORCH_CONTAINER,
)


@pytest.mark.parametrize(
    "container_per_test",
    [OLLAMA_CONTAINER],
    indirect=["container_per_test"],
)
def test_ollama_health(container_per_test):
    """Test that we can reach the port 11434 successfully."""
    host_port = container_per_test.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_ollama_response():
        resp = requests.get(f"http://localhost:{host_port}/", timeout=30)
        resp.raise_for_status()
        assert "Ollama is running" in resp.text

    check_ollama_response()


@pytest.mark.parametrize(
    "container_per_test",
    [OPENWEBUI_CONTAINER],
    indirect=["container_per_test"],
)
def test_openwebui_health(container_per_test):
    """Test that we can reach the port 8080 successfully."""
    host_port = container_per_test.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_openwebui_response():
        resp = requests.get(f"http://localhost:{host_port}/health", timeout=30)
        resp.raise_for_status()
        assert ":true" in resp.text

    check_openwebui_response()


@pytest.mark.parametrize(
    "container_per_test",
    [MILVUS_CONTAINER],
    indirect=["container_per_test"],
)
def test_milvus_health(container_per_test):
    """Test the milvus container."""

    # doesn't allow running outside kubernetes as far as I can see
    container_per_test.connection.check_output(
        "minio-client -q --dp --version"
    )
    container_per_test.connection.check_output("etcd --version")
    container_per_test.connection.check_output("milvus")


@pytest.mark.parametrize(
    "container",
    [PYTORCH_CONTAINER],
    indirect=["container"],
)
def test_pytorch_health(container):
    """Test the pytorch container."""

    # chech pytorch Version
    container.connection.check_output(
        "python3.11 -c 'import torch; print(torch.__version__)'"
    )
    container.connection.check_output("git --version")
