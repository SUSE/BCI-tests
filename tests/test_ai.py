"""This module contains the tests for the SUSE AI container."""

import pytest
import requests
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import LMCACHE_LMSTACK_ROUTER_CONTAINER
from bci_tester.data import LMCACHE_VLLM_OPENAI_CONTAINER
from bci_tester.data import MCPO_CONTAINER
from bci_tester.data import MILVUS_CONTAINER
from bci_tester.data import OLLAMA_CONTAINER
from bci_tester.data import OPENWEBUI_CONTAINER
from bci_tester.data import OPENWEBUI_PIPELINES_CONTAINER
from bci_tester.data import PYTORCH_CONTAINER
from bci_tester.data import SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME
from bci_tester.data import SUSE_AI_OBSERVABILITY_EXTENSION_SETUP
from bci_tester.data import VLLM_OPENAI_CONTAINER

CONTAINER_IMAGES = (
    OLLAMA_CONTAINER,
    OPENWEBUI_CONTAINER,
    MILVUS_CONTAINER,
    MCPO_CONTAINER,
    PYTORCH_CONTAINER,
    SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME,
    SUSE_AI_OBSERVABILITY_EXTENSION_SETUP,
    OPENWEBUI_PIPELINES_CONTAINER,
    VLLM_OPENAI_CONTAINER,
    LMCACHE_LMSTACK_ROUTER_CONTAINER,
    LMCACHE_VLLM_OPENAI_CONTAINER,
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
    [OPENWEBUI_PIPELINES_CONTAINER],
    indirect=["container_per_test"],
)
def test_pipelines_health(container_per_test):
    """Test that we can reach the port 9099 successfully."""
    host_port = container_per_test.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_pipelines_response():
        resp = requests.get(f"http://localhost:{host_port}/", timeout=30)
        resp.raise_for_status()
        assert ":true" in resp.text

    check_pipelines_response()


@pytest.mark.parametrize(
    "container",
    [VLLM_OPENAI_CONTAINER],
    indirect=["container"],
)
def test_vllm_health(container):
    """Test the vLLM container."""

    # check vLLM version
    container.connection.check_output(
        "python3.11 -c 'import vllm; print(vllm.__version__)'"
    )


@pytest.mark.parametrize(
    "container",
    [LMCACHE_VLLM_OPENAI_CONTAINER],
    indirect=["container"],
)
def test_lmcache_vllm_health(container):
    """Test the LMCache vLLM container."""

    # check vLLM version
    container.connection.check_output(
        "python3.11 -c 'import vllm; print(vllm.__version__)'"
    )
    # check LMCache version
    container.connection.check_output(
        "python3.11 -c 'import lmcache._version; print(lmcache._version.__version__)'"
    )


@pytest.mark.parametrize(
    "container",
    [LMCACHE_LMSTACK_ROUTER_CONTAINER],
    indirect=["container"],
)
def test_lmstack_router_health(container):
    """Test the LMCache LMStack Router container."""

    # check vLLM Router version
    container.connection.check_output(
        "python3.11 -c 'import vllm_router._version; print(vllm_router._version.__version__)'"
    )


@pytest.mark.parametrize(
    "container_per_test",
    [MCPO_CONTAINER],
    indirect=["container_per_test"],
)
def test_mcpo_health(container_per_test):
    """Test that we can reach the port 8000 successfully."""
    host_port = container_per_test.forwarded_ports[0].host_port

    # Retry 5 times with exponential backoff delay
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def check_mcpo_response():
        resp = requests.get(f"http://localhost:{host_port}/docs", timeout=30)
        resp.raise_for_status()
        assert "mcp-time" in resp.text

    check_mcpo_response()
