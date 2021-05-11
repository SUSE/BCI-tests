import json
import os
from types import SimpleNamespace

with open(
    os.path.join(os.path.dirname(__file__), "data", "containers.json"), "r"
) as dataf:
    # Might need another decoder to have convenience functions
    containers = json.load(dataf, object_hook=lambda d: SimpleNamespace(**d))

# TODO: With another decoder, make sure that if someone gives registry, it's using it, else it's using the default one from CONTAINER_REGISTRY
CONTAINER_REGISTRY = "registry.opensuse.org"
