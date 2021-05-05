from dataclasses import dataclass
from typing import Dict, List, Optional


go_containers = {
    "1.16": "registry.opensuse.org/devel/bci/images/bci/golang-devel:16",
    "1.15": "registry.opensuse.org/devel/bci/images/bci/golang-devel:15",
    "1.14": "registry.opensuse.org/devel/bci/images/bci/golang-devel:14",
}
node_containers = {
    "15": "registry.opensuse.org/home/fcrozat/matryoshka/containers_node15/node15:latest",
    "14": "registry.opensuse.org/home/fcrozat/matryoshka/containers_node14/node14:latest",
    "12": "registry.opensuse.org/home/fcrozat/matryoshka/containers_node12/node12:latest",
}
openjdk_devel_containers = {
    "16": "registry.opensuse.org/devel/bci/images/bci/openjdk-devel:16",
    "15": "registry.opensuse.org/devel/bci/images/bci/openjdk-devel:15",
    "14": "registry.opensuse.org/devel/bci/images/bci/openjdk-devel:14",
    "11": "registry.opensuse.org/devel/bci/images/bci/openjdk-devel:11",
}
openjdk_containers = {
    "16": "registry.opensuse.org/devel/bci/images/bci/openjdk:16",
    "15": "registry.opensuse.org/devel/bci/images/bci/openjdk:15",
    "14": "registry.opensuse.org/devel/bci/images/bci/openjdk:14",
    "11": "registry.opensuse.org/devel/bci/images/bci/openjdk:11",
}
python_containers = {
    "3.9": "registry.opensuse.org/home/fcrozat/matryoshka/containers_python39/python39:latest",
    "3.8": "registry.opensuse.org/home/fcrozat/matryoshka/containers_python38/python38:latest",
    "3.6": "registry.opensuse.org/home/fcrozat/matryoshka/containers_python36/python36:latest",
}


@dataclass
class VersionedLanguageContainer:
    """
    Storage class representing a single container that is built in the Open
    Build Service, published into a repository and represents a language or
    tech stack at a certain version (that needn't match the container tag).
    """

    #: name of the project in the build service where the container is built
    project: str
    #: repository in which the container is published
    repository: str
    #: the version of this container
    version: str
    #: name and tag/version of this container
    name_and_tag: str
    #: optional prefix appended to the full url after the repository
    prefix: Optional[str] = None
    #: url of the registry under which the build service publishes OCI images
    registry_base_url: str = "registry.opensuse.org/"

    def __post_init__(self) -> None:
        if self.registry_base_url[-1] != "/":
            self.registry_base_url = self.registry_base_url + "/"

    @property
    def full_url(self) -> str:
        if len(self.name_and_tag.split(":")) not in (1, 2):
            raise ValueError(
                f"got an invalid value for {self.name_and_tag=}, "
                "contains a wrong number of ':'"
            )
        elements = [self.project.replace(":", "/"), self.repository]
        if self.prefix:
            elements.append(self.prefix)
        elements.append(self.name_and_tag)
        return self.registry_base_url + "/".join(
            elem.strip("/") for elem in elements
        )

    def __str__(self) -> str:
        return self.full_url

    def __repr__(self) -> str:
        return f"{self.name_and_tag} from {self.project}/{self.repository}"


def container_from_url(
    url: str, version: Optional[str] = None, url_includes_prefix: bool = False
) -> VersionedLanguageContainer:
    """"""
    path_elements = url.split("/")
    name_and_tag = path_elements[-1]

    repository_index = -3 if url_includes_prefix else -2
    repository = path_elements[repository_index]
    registry_base_url = path_elements[0]
    prefix = path_elements[-2] if url_includes_prefix else None
    lang_container = VersionedLanguageContainer(
        project=":".join(path_elements[1:repository_index]),
        repository=repository,
        version=version or name_and_tag.split(":")[1],
        name_and_tag=name_and_tag,
        prefix=prefix,
        registry_base_url=registry_base_url,
    )

    assert lang_container.full_url == url, (
        f"original url '{url}' and reconstructed url "
        + f"'{lang_container.full_url}' do not match"
    )

    return lang_container


containers: Dict[str, List[VersionedLanguageContainer]] = {
    "go": [
        container_from_url(url, version, url_includes_prefix=True)
        for version, url in go_containers.items()
    ],
    "node": [
        container_from_url(url, version, False)
        for version, url in node_containers.items()
    ],
    "openjdk": [
        container_from_url(url) for url in openjdk_containers.values()
    ],
    "openjdk-devel": [
        container_from_url(url) for url in openjdk_devel_containers.values()
    ],
    "python": [
        container_from_url(url, version, False)
        for version, url in python_containers.items()
    ],
}
