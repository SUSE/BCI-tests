import json
import os

DEFAULT_REGISTRY = "registry.opensuse.org"


class Container:
    def __init__(self, **kwargs):
        # TODO (maybe?) add type validation?
        self.type = kwargs["type"]
        self.repo = kwargs["repo"]
        self.image = kwargs["image"]
        self.tag = kwargs["tag"]
        self.version = kwargs.get("version", kwargs["tag"])
        self.name = kwargs.get("name", f"{self.type}-{self.version}")
        self.registry = kwargs.get("registry", DEFAULT_REGISTRY)
        self.url = kwargs.get(
            "url", f"{self.registry}/{self.repo}/{self.image}:{self.tag}"
        )

    def __repr__(self):
        return f"Container: {self.name} URL: {self.url}"


with open(
    os.path.join(os.path.dirname(__file__), "data", "containers.json"), "r"
) as dataf:
    containers = json.load(dataf, object_hook=lambda d: Container(**d))
