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
from bci_tester.data import SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME_CONTAINER
from bci_tester.data import SUSE_AI_OBSERVABILITY_EXTENSION_SETUP_CONTAINER

CONTAINER_IMAGES = (
    OLLAMA_CONTAINER,
    OPENWEBUI_CONTAINER,
    MILVUS_CONTAINER,
    PYTORCH_CONTAINER,
    SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME_CONTAINER,
    SUSE_AI_OBSERVABILITY_EXTENSION_SETUP_CONTAINER,
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


@pytest.mark.parametrize(
    "container_per_test",
    [SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME_CONTAINER],
    indirect=["container_per_test"],
)
def test_suse_ai_observability_extenstion_runtime_health(container_per_test):
    """Test the SUSE AI Observability Extension runtime container."""

    # the container is not meant to run outside kubernetes, only basic checks will be performed
    # it's expected to fail without configuration provided by environment variables
    result = container_per_test.connection.run_expect(
        [1], "/usr/bin/suse-ai-observability-extension-runtime"
    )
    assert (
        "failed to initialize error=\"Key: 'Configuration.StackState'"
        in result.stderr
    )
    assert "Key: 'Configuration.Kubernetes.Cluster'" in result.stderr


@pytest.mark.parametrize(
    "container_per_test",
    [SUSE_AI_OBSERVABILITY_EXTENSION_SETUP_CONTAINER],
    indirect=["container_per_test"],
)
def test_suse_ai_observability_extenstion_setup_health(container_per_test):
    """Test the SUSE AI Observability Extension setup container."""

    # the container is not meant to run outside kubernetes, only basic checks will be performed
    # check that the necessary tools are available
    container_per_test.connection.check_output("sts")
    container_per_test.connection.check_output("jq")

    # check that the necessary files are available
    expected_files = [
        "mnt/init.sh",
        "mnt/menu/llm.yaml",
        "mnt/overview/genai_system.yaml",
        "mnt/overview/gpu_nodes.yaml",
        "mnt/overview/vector_db_system.yaml",
        "mnt/overview/genai_apps.yaml",
        "mnt/components/genai_system_ollama.yaml",
        "mnt/components/genai_system_openai.yaml",
        "mnt/components/genai_dbsystem_milvus.yaml",
        "mnt/metrics/gpu_nodes.yaml",
        "mnt/metrics/gpu_pods.yaml",
        "mnt/metrics/genai_systems.yaml",
        "mnt/metrics/db_systems.yaml",
        "mnt/metrics/genai_apps.yaml",
    ]

    for file in expected_files:
        assert container_per_test.connection.file(file).is_file, (
            f"{file} not found"
        )
