import json
import os
from dataclasses import dataclass


DEFAULT_REGISTRY = "registry.opensuse.org"


@dataclass
class Container:
    type: str
    repo: str
    image: str
    tag: str
    version: str = ""
    name: str = ""
    registry: str = DEFAULT_REGISTRY
    url: str = ""

    def __post_init__(self):
        if not self.version:
            self.version = self.tag
        if not self.name:
            self.name = f"{self.type}-{self.version}"
        if not self.url:
            self.url = f"{self.registry}/{self.repo}/{self.image}:{self.tag}"


with open(
    os.path.join(os.path.dirname(__file__), "data", "containers.json"), "r"
) as dataf:
    containers = json.load(dataf, object_hook=lambda d: Container(**d))
