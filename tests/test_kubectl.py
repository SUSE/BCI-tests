"""This module tests the kubectl container."""

## Maintainer: BCI team (#proj-bci)

import json

import pytest

from bci_tester.data import KUBECTL_CONTAINERS


@pytest.mark.parametrize(
    "container_per_test",
    KUBECTL_CONTAINERS,
    indirect=["container_per_test"],
)
def test_kubectl_binary(container_per_test) -> None:
    expected_json = json.loads("""{
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
}""")
    output = container_per_test.connection.check_output(
        "kubectl create deployment nginx --image=nginx --dry-run=client -o json"
    ).strip()
    json_out = json.loads(output)
    assert json_out == expected_json
