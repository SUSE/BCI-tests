import os
import shlex
import tempfile
from dataclasses import dataclass
from dataclasses import field
from string import Template
from subprocess import check_output
from typing import List
from typing import Optional
from typing import Union

from bci_tester.helpers import get_selected_runtime


DEFAULT_REGISTRY = "registry.suse.de"
EXTRA_RUN_ARGS = shlex.split(os.getenv("EXTRA_RUN_ARGS", ""))
EXTRA_BUILD_ARGS = shlex.split(os.getenv("EXTRA_BUILD_ARGS", ""))

OS_VERSION = "15.3"
OS_PRETTY_NAME = "SUSE Linux Enterprise Server 15 SP3"


@dataclass
class ContainerBase:
    #: full url to this container via which it can be pulled
    url: str = ""

    #: id of the container if it is not available via a registry URL
    container_id: str = ""

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

    def __str__(self) -> str:
        return self.url or self.container_id

    @property
    def entry_point(self) -> Optional[str]:
        """The entry point of this container, either its default, bash or a
        custom one depending on the set values. A custom entry point is
        preferred, otherwise bash is used unles `self.default_entry_point` is
        `True`.
        """
        if self.custom_entry_point:
            return self.custom_entry_point
        if self.default_entry_point:
            return None
        return "/bin/bash"

    @property
    def launch_cmd(self) -> List[str]:
        """Returns the command to launch this container image (excluding the
        leading podman or docker binary name).
        """
        cmd = ["run", "-d"] + EXTRA_RUN_ARGS + self.extra_launch_args

        if self.entry_point is None:
            cmd.append(self.container_id or self.url)
        else:
            cmd += ["-it", self.container_id or self.url, self.entry_point]

        return cmd


@dataclass
class Container(ContainerBase):
    """This class stores information about the BCI images under test.

    Instances of this class are constructed from the contents of
    data/containers.json
    """

    repo: str = ""
    image: str = ""
    tag: str = "latest"
    version: str = ""
    registry: str = DEFAULT_REGISTRY

    def __post_init__(self):
        for val, name in ((self.repo, "repo"), (self.image, "image")):
            if not val:
                raise ValueError(f"property {name} must be set")
        if not self.version:
            self.version = self.tag
        if not self.url:
            self.url = f"{self.registry}/{self.repo}/{self.image}:{self.tag}"

    def pull_container(self) -> None:
        """Pulls the container with the given url using the currently selected
        container runtime"""
        runtime = get_selected_runtime()
        check_output([runtime.runner_binary, "pull", self.url])

    def prepare_container(self) -> None:
        """Prepares the container so that it can be launched."""
        self.pull_container()

    def get_base_url(self) -> str:
        return self.url


@dataclass
class DerivedContainer(ContainerBase):
    base: Union[Container, "DerivedContainer"] = None
    containerfile: str = ""

    def __str__(self) -> str:
        return (
            self.container_id
            or f"container derived from {self.base.__str__()}"
        )

    def get_base_url(self) -> str:
        return self.base.get_base_url()

    def prepare_container(self) -> None:
        self.base.prepare_container()

        runtime = get_selected_runtime()
        with tempfile.TemporaryDirectory() as tmpdirname:
            containerfile_path = os.path.join(tmpdirname, "Dockerfile")
            with open(containerfile_path, "w") as containerfile:
                from_id = (
                    getattr(self.base, "url", self.base.container_id)
                    or self.base.container_id
                )
                assert from_id
                containerfile.write(
                    f"""FROM {from_id}
{self.containerfile}
"""
                )

            self.container_id = runtime.get_image_id_from_stdout(
                check_output(
                    runtime.build_command + EXTRA_BUILD_ARGS + [tmpdirname]
                )
                .decode()
                .strip()
            )


@dataclass
class MultiStageBuild:
    builder: Union[Container, DerivedContainer]
    runner: Union[Container, DerivedContainer, str]

    dockerfile_template: str

    @property
    def dockerfile(self) -> str:
        builder = self.builder.container_id or self.builder.url
        runner = (
            self.runner
            if isinstance(self.runner, str)
            else self.runner.container_id or self.runner.url
        )

        return Template(self.dockerfile_template).substitute(
            builder=builder, runner=runner
        )

    def prepare_build(self, tmp_dir):
        self.builder.prepare_container()
        if not isinstance(self.runner, str):
            self.runner.prepare_container()

        with open(tmp_dir / "Dockerfile", "w") as dockerfile:
            dockerfile.write(self.dockerfile)


BASE_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/cr/totest/images",
    image="suse/sle15",
    tag=OS_VERSION,
)
MINIMAL_CONTAINER = Container(
    repo="suse/sle-15-sp3/update/bci/images",
    image="bci/minimal",
    tag=OS_VERSION,
)
MICRO_CONTAINER = Container(
    repo="suse/sle-15-sp3/update/bci/images",
    image="bci/micro",
    tag=OS_VERSION,
)

GO_1_16_BASE_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images", image="bci/golang", tag="1.16"
)

OPENJDK_BASE_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images", image="bci/openjdk", tag="11"
)
OPENJDK_DEVEL_BASE_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images",
    image="bci/openjdk-devel",
    tag="11",
)
NODEJS_12_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images", image="bci/nodejs", tag="12"
)
NODEJS_14_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images", image="bci/nodejs", tag="14"
)

PYTHON36_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images", image="bci/python", tag="3.6"
)
PYTHON39_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images", image="bci/python", tag="3.9"
)

DOTNET_SDK_3_1_BASE_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/cr/totest/images",
    image="suse/dotnet-sdk",
    tag="3.1",
)
DOTNET_SDK_5_0_BASE_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/cr/totest/images",
    image="suse/dotnet-sdk",
    tag="5.0",
)

DOTNET_ASPNET_3_1_BASE_CONTAINER: Union[
    Container, DerivedContainer
] = Container(
    repo="suse/sle-15-sp3/update/cr/totest/images",
    image="suse/dotnet-aspnet",
    tag="3.1",
)
DOTNET_ASPNET_5_0_BASE_CONTAINER: Union[
    Container, DerivedContainer
] = Container(
    repo="suse/sle-15-sp3/update/cr/totest/images",
    image="suse/dotnet-aspnet",
    tag="5.0",
)

INIT_CONTAINER: Union[Container, DerivedContainer] = Container(
    repo="suse/sle-15-sp3/update/bci/images",
    image="bci/init",
    extra_launch_args=[
        "--privileged",
        # need to give the container access to dbus when invoking tox via sudo,
        # because then things get weird...
        # see:
        # https://askubuntu.com/questions/1297226/how-to-run-systemctl-command-inside-docker-container
        "-v",
        "/var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket",
    ],
)

#
# !! IMPORTANT !!
# ===============
#
# All "base" containers which get pre-configured with the SLE_BCI repository
# should be put into this if branch so that their repository gets replaced on
# setting the `BCI_DEVEL_REPO` environment variable.
#
# We must not run any zypper commands here, as otherwise container-suseconnect
# will keep a ton of metadata of the fetched repositories (which is a lot on
# registered systems)
#
BCI_DEVEL_REPO = os.getenv("BCI_DEVEL_REPO")
if BCI_DEVEL_REPO is not None:
    REPLACE_REPO_CONTAINERFILE = f"RUN sed -i 's|baseurl.*|baseurl={BCI_DEVEL_REPO}|' /etc/zypp/repos.d/SLE_BCI.repo"

    (
        BASE_CONTAINER_WITH_DEVEL_REPO,
        GO_1_16_BASE_CONTAINER_WITH_DEVEL_REPO,
        OPENJDK_BASE_CONTAINER_WITH_DEVEL_REPO,
        OPENJDK_DEVEL_BASE_CONTAINER_WITH_DEVEL_REPO,
        NODEJS_12_CONTAINER_WITH_DEVEL_REPO,
        NODEJS_14_CONTAINER_WITH_DEVEL_REPO,
        PYTHON36_CONTAINER_WITH_DEVEL_REPO,
        PYTHON39_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_SDK_3_1_BASE_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_SDK_5_0_BASE_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_ASPNET_3_1_BASE_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_ASPNET_5_0_BASE_CONTAINER_WITH_DEVEL_REPO,
        INIT_CONTAINER_WITH_DEVEL_REPO,
    ) = (
        DerivedContainer(base=cont, containerfile=REPLACE_REPO_CONTAINERFILE)
        for cont in (
            BASE_CONTAINER,
            GO_1_16_BASE_CONTAINER,
            OPENJDK_BASE_CONTAINER,
            OPENJDK_DEVEL_BASE_CONTAINER,
            NODEJS_12_CONTAINER,
            NODEJS_14_CONTAINER,
            PYTHON36_CONTAINER,
            PYTHON39_CONTAINER,
            DOTNET_SDK_3_1_BASE_CONTAINER,
            DOTNET_SDK_5_0_BASE_CONTAINER,
            DOTNET_ASPNET_3_1_BASE_CONTAINER,
            DOTNET_ASPNET_5_0_BASE_CONTAINER,
            INIT_CONTAINER,
        )
    )

    (
        BASE_CONTAINER,
        GO_1_16_BASE_CONTAINER,
        OPENJDK_BASE_CONTAINER,
        OPENJDK_DEVEL_BASE_CONTAINER,
        NODEJS_12_CONTAINER,
        NODEJS_14_CONTAINER,
        PYTHON36_CONTAINER,
        PYTHON39_CONTAINER,
        DOTNET_SDK_3_1_BASE_CONTAINER,
        DOTNET_SDK_5_0_BASE_CONTAINER,
        DOTNET_ASPNET_3_1_BASE_CONTAINER,
        DOTNET_ASPNET_5_0_BASE_CONTAINER,
        INIT_CONTAINER,
    ) = (
        BASE_CONTAINER_WITH_DEVEL_REPO,
        GO_1_16_BASE_CONTAINER_WITH_DEVEL_REPO,
        OPENJDK_BASE_CONTAINER_WITH_DEVEL_REPO,
        OPENJDK_DEVEL_BASE_CONTAINER_WITH_DEVEL_REPO,
        NODEJS_12_CONTAINER_WITH_DEVEL_REPO,
        NODEJS_14_CONTAINER_WITH_DEVEL_REPO,
        PYTHON36_CONTAINER_WITH_DEVEL_REPO,
        PYTHON39_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_SDK_3_1_BASE_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_SDK_5_0_BASE_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_ASPNET_3_1_BASE_CONTAINER_WITH_DEVEL_REPO,
        DOTNET_ASPNET_5_0_BASE_CONTAINER_WITH_DEVEL_REPO,
        INIT_CONTAINER_WITH_DEVEL_REPO,
    )

BCI_DEVEL_REPO = (
    BCI_DEVEL_REPO
    or "https://updates.suse.com/SUSE/Products/SLE-BCI/15-SP3/x86_64/product/"
)
REPOCLOSURE_CONTAINER = DerivedContainer(
    base=Container(
        url="registry.fedoraproject.org/fedora:latest",
        registry="registry.fedoraproject.org",
        repo="unused",
        image="fedora",
    ),
    containerfile=r"""RUN dnf -y install 'dnf-command(repoclosure)'
RUN rm -f /etc/yum.repos.d/*repo
RUN echo $'[SLE_BCI] \n\
enabled=1 \n\
name="SLE BCI" \n\
autorefresh=0 \n\
baseurl="""
    + BCI_DEVEL_REPO
    + r""" \n\
priority=100' > /etc/yum.repos.d/SLE_BCI.repo
""",
)

#: Containers that are directly pulled from registry.suse.de
BASE_CONTAINERS = [
    BASE_CONTAINER,
    MINIMAL_CONTAINER,
    MICRO_CONTAINER,
    GO_1_16_BASE_CONTAINER,
    OPENJDK_BASE_CONTAINER,
    OPENJDK_DEVEL_BASE_CONTAINER,
    NODEJS_12_CONTAINER,
    NODEJS_14_CONTAINER,
    PYTHON36_CONTAINER,
    PYTHON39_CONTAINER,
    DOTNET_SDK_3_1_BASE_CONTAINER,
    DOTNET_SDK_5_0_BASE_CONTAINER,
    DOTNET_ASPNET_3_1_BASE_CONTAINER,
    DOTNET_ASPNET_5_0_BASE_CONTAINER,
    INIT_CONTAINER,
]


GO_1_16_CONTAINER = DerivedContainer(
    base=GO_1_16_BASE_CONTAINER, containerfile="""RUN zypper -n in make"""
)


ALL_CONTAINERS = BASE_CONTAINERS + [GO_1_16_CONTAINER]
