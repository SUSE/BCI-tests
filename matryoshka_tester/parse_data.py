import json
import os
from dataclasses import dataclass
from typing import List


DEFAULT_REGISTRY = "registry.opensuse.org"
DEFAULT_CONTAINERS = os.path.join(
    os.path.dirname(__file__), "data", "containers.json"
)


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


def build_containerlist(filename: str = DEFAULT_CONTAINERS) -> List[Container]:
    with open(filename, "r") as dataf:
        return json.load(dataf, object_hook=lambda d: Container(**d))


containers = build_containerlist()
