import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


DEFAULT_REGISTRY = "registry.suse.de"
DEFAULT_CONTAINERS = os.path.join(
    os.path.dirname(__file__), "data", "containers.json"
)


@dataclass
class Container:
    """This class stores information about the BCI images under test.

    Instances of this class are constructed from the contents of
    data/containers.json
    """

    type: str
    repo: str
    image: str
    tag: str
    version: str = ""
    name: str = ""
    registry: str = DEFAULT_REGISTRY
    url: str = ""

    #: flag whether the image should be launched using its own defined entry
    #: point. If False, then ``/bin/bash`` is used.
    default_entry_point: bool = False

    #: custom entry point for this container (i.e. neither its default, nor
    #: `/bin/bash`)
    custom_entry_point: Optional[str] = None

    #: List of additional flags that will be inserted after
    #: `docker/podman run -d`. The list must be properly escaped, e.g. as
    #: created by `shlex.split`
    extra_launch_args: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.version:
            self.version = self.tag
        if not self.name:
            self.name = f"{self.type}-{self.version}"
        if not self.url:
            self.url = f"{self.registry}/{self.repo}/{self.image}:{self.tag}"

    @property
    def entry_point(self) -> Optional[str]:
        """The entry point of this container, either its default, bash or a
        custom one depending on the set values. A custom entry point is
        preferred, otherwise bash is used unles `self.default_entry_point` is
        `True`.
        """
        if self.custom_entry_point:
            return self.custom_entry_point
        elif self.default_entry_point:
            return None
        else:
            return "/bin/bash"

    @property
    def launch_cmd(self) -> List[str]:
        """Returns the command to launch this container image (excluding the
        leading podman or docker binary name).
        """
        cmd = ["run", "-d"] + self.extra_launch_args

        if self.entry_point is None:
            cmd.append(self.url)
        else:
            cmd += ["-it", self.url, self.entry_point]

        return cmd


def build_containerlist(filename: str = DEFAULT_CONTAINERS) -> List[Container]:
    with open(filename, "r") as dataf:
        return json.load(dataf, object_hook=lambda d: Container(**d))


containers: List[Container] = build_containerlist()


def get_container_by_type_tag(type: str, tag: str) -> Container:
    matching_containers = [
        c for c in containers if c.type == type and c.tag == tag
    ]
    assert len(matching_containers) == 1, (
        f"expected to find 1 container with the type {type} and tag {tag}, "
        f"but got {len(matching_containers)} matches"
    )
    return matching_containers[0]
