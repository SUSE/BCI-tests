import json
from subprocess import check_output
from typing import Any
from typing import Union

import pytest
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BASE_CONTAINERS
from bci_tester.data import Container
from bci_tester.data import DerivedContainer
from bci_tester.data import DOTNET_ASPNET_3_1_BASE_CONTAINER
from bci_tester.data import DOTNET_ASPNET_5_0_BASE_CONTAINER
from bci_tester.data import DOTNET_SDK_3_1_BASE_CONTAINER
from bci_tester.data import DOTNET_SDK_5_0_BASE_CONTAINER
from bci_tester.data import GO_1_16_BASE_CONTAINER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import NODEJS_12_CONTAINER
from bci_tester.data import NODEJS_14_CONTAINER
from bci_tester.data import OPENJDK_BASE_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_BASE_CONTAINER
from bci_tester.data import OS_PRETTY_NAME
from bci_tester.data import OS_VERSION
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import PYTHON39_CONTAINER
from bci_tester.helpers import LOCALHOST
from bci_tester.helpers import OciRuntimeBase


TITLE = "SUSE Linux Enterprise Server 15 SP3"
VENDOR = "SUSE LLC"
URL = "https://www.suse.com/products/server/"


IMAGES_AND_NAMES = [
    (BASE_CONTAINER, "base"),
    (MINIMAL_CONTAINER, "minimal"),
    (MICRO_CONTAINER, "micro"),
    (GO_1_16_BASE_CONTAINER, "golang"),
    (OPENJDK_BASE_CONTAINER, "openjdk"),
    (OPENJDK_DEVEL_BASE_CONTAINER, "openjdk.devel"),
    (NODEJS_12_CONTAINER, "nodejs"),
    (NODEJS_14_CONTAINER, "nodejs"),
    (PYTHON36_CONTAINER, "python"),
    (PYTHON39_CONTAINER, "python"),
    (INIT_CONTAINER, "init"),
] + (
    [
        (DOTNET_SDK_3_1_BASE_CONTAINER, "dotnet.sdk"),
        (DOTNET_SDK_5_0_BASE_CONTAINER, "dotnet.sdk"),
        (DOTNET_ASPNET_3_1_BASE_CONTAINER, "dotnet.aspnet"),
        (DOTNET_ASPNET_5_0_BASE_CONTAINER, "dotnet.aspnet"),
    ]
    if LOCALHOST.system_info.arch == "x86_64"
    else []
)

assert len(BASE_CONTAINERS) == len(
    IMAGES_AND_NAMES
), "IMAGES_AND_NAMES must have all containers from BASE_CONTAINERS"


def get_container_metadata(
    container_data: Union[Container, DerivedContainer]
) -> Any:
    return json.loads(
        check_output(
            [
                "skopeo",
                "inspect",
                f"docker://{container_data.get_base().url}",
            ],
        )
        .decode()
        .strip()
    )


@pytest.mark.parametrize(
    "container_data,container_name",
    [(img, name) for (img, name) in IMAGES_AND_NAMES if img != BASE_CONTAINER]
    + [
        pytest.param(
            BASE_CONTAINER,
            "base",
            marks=pytest.mark.xfail(
                reason="The base container has no com.suse.bci.base labels yet"
            ),
        )
    ],
)
def test_general_labels(
    container_data: Union[Container, DerivedContainer],
    container_name: str,
):
    metadata = get_container_metadata(container_data)

    assert metadata["Name"] == container_data.get_base().url.split(":")[0]

    labels = metadata["Labels"]
    version = getattr(container_data, "tag") or container_data.get_base().tag

    for prefix in (
        f"com.suse.bci.{container_name}",
        "org.opencontainers.image",
    ):
        assert TITLE in labels[f"{prefix}.title"]
        assert OS_PRETTY_NAME in labels[f"{prefix}.description"]
        if version == "latest":
            assert OS_VERSION in labels[f"{prefix}.version"]
        else:
            version == labels[f"{prefix}.version"]
        assert labels[f"{prefix}.url"] == URL
        assert labels[f"{prefix}.vendor"] == VENDOR


@pytest.mark.parametrize(
    "container_data,container_name",
    [(img, name) for (img, name) in IMAGES_AND_NAMES if img != BASE_CONTAINER]
    + [
        pytest.param(
            BASE_CONTAINER,
            "base",
            marks=pytest.mark.xfail(
                reason="The base container has no com.suse.bci.base labels yet"
            ),
        )
    ],
)
def test_disturl(
    container_data: Union[Container, DerivedContainer], container_name: str
):
    labels = get_container_metadata(container_data)["Labels"]

    disturl = labels["org.openbuildservice.disturl"]

    assert disturl == labels[f"com.suse.bci.{container_name}.disturl"]
    assert "obs://build.suse.de/SUSE:SLE-15-SP3:Update" in disturl


@pytest.mark.skipif(
    not LOCALHOST.exists("osc"),
    reason="osc needs to be installed for this test",
)
@pytest.mark.parametrize("container_data", BASE_CONTAINERS)
def test_disturl_can_be_checked_out(
    container_data: Union[Container, DerivedContainer],
    tmp_path,
):
    labels = get_container_metadata(container_data)["Labels"]

    disturl = labels["org.openbuildservice.disturl"]
    check_output(["osc", "co", disturl], cwd=tmp_path)


@pytest.mark.parametrize(
    "container_data",
    [cont for cont in BASE_CONTAINERS if cont != BASE_CONTAINER],
)
def test_techpreview_label(container_data: Union[Container, DerivedContainer]):
    metadata = get_container_metadata(container_data)
    assert (
        metadata["Labels"]["com.suse.techpreview"] == "1"
    ), "images must be marked as techpreview"


@pytest.mark.parametrize(
    "container_data,container_name",
    [(img, name) for (img, name) in IMAGES_AND_NAMES if img != BASE_CONTAINER]
    + [
        pytest.param(
            BASE_CONTAINER,
            "base",
            marks=pytest.mark.xfail(
                reason="The base container has no com.suse.bci.base labels yet"
            ),
        )
    ],
)
def test_reference(
    container_data: Union[Container, DerivedContainer],
    container_name: str,
    container_runtime: OciRuntimeBase,
):
    labels = get_container_metadata(container_data)["Labels"]

    reference = labels["org.opensuse.reference"]
    assert labels[f"com.suse.bci.{container_name}.reference"] == reference
    assert container_name.replace(".", "-") in reference

    if "registry.suse.com/suse/" in reference:
        check_output([container_runtime.runner_binary, "pull", reference])
