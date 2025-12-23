"""Test the kubernetes client (kubectl) BCI application container images."""

import json

import pytest

from bci_tester.data import KUBECTL_CONTAINERS

_OLD_KUBECTL_JSON = """{
    "kind": "Deployment",
    "apiVersion": "apps/v1",
    "metadata": {
        "name": "nginx",
        "creationTimestamp": null,
        "labels": {
            "app": "nginx"
        }
    },
    "spec": {
        "replicas": 1,
        "selector": {
            "matchLabels": {
                "app": "nginx"
            }
        },
        "template": {
            "metadata": {
                "creationTimestamp": null,
                "labels": {
                    "app": "nginx"
                }
            },
            "spec": {
                "containers": [
                    {
                        "name": "nginx",
                        "image": "nginx",
                        "resources": {}
                    }
                ]
            }
        },
        "strategy": {}
    },
    "status": {}
}"""

_KUBECTL_134_JSON = """{
    "kind": "Deployment",
    "apiVersion": "apps/v1",
    "metadata": {
        "name": "nginx",
        "labels": {
            "app": "nginx"
        }
    },
    "spec": {
        "replicas": 1,
        "selector": {
            "matchLabels": {
                "app": "nginx"
            }
        },
        "template": {
            "metadata": {
                "labels": {
                    "app": "nginx"
                }
            },
            "spec": {
                "containers": [
                    {
                        "name": "nginx",
                        "image": "nginx",
                        "resources": {}
                    }
                ]
            }
        },
        "strategy": {}
    },
    "status": {}
}"""


@pytest.mark.parametrize(
    "container_per_test",
    KUBECTL_CONTAINERS,
    indirect=["container_per_test"],
)
def test_kubectl_binary(container_per_test) -> None:
    """Test that the kubectl binary behaves like expected (mocked)"""
    version = json.loads(
        container_per_test.connection.check_output(
            "kubectl version --client=true -o json"
        )
    )
    expected_json = json.loads(
        _KUBECTL_134_JSON
        if int(version["clientVersion"]["minor"]) >= 34
        else _OLD_KUBECTL_JSON
    )
    output = container_per_test.connection.check_output(
        "kubectl create deployment nginx --image=nginx --dry-run=client -o json"
    ).strip()
    json_out = json.loads(output)
    assert json_out == expected_json


@pytest.mark.parametrize(
    "container_per_test",
    KUBECTL_CONTAINERS,
    indirect=["container_per_test"],
)
def test_diff_available(container_per_test) -> None:
    """Test for diff being embedded in the container - necessary for kubectl diff"""
    output = container_per_test.connection.check_output(
        "diff --version"
    ).strip()
    assert "GNU diffutils" in output
