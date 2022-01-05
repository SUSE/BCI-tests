"""Verification of the container metadata that are available via the registry
leveraging mostly :command:`skopeo`.

These tests are host OS independent and it is thus not necessary to run them on
a non-x86_64 host.

**CAUTION:** The tests should be run on x86_64, as the .Net images are only
available on that platform.

The tests in this module are mostly testing the image labels. We follow the
conventions outlined in
`<https://confluence.suse.com/display/ENGCTNRSTORY/BCI+image+labels>`_. But have
to skip some of the tests for the SLE 15 SP3 base container, as it does not
offer the labels under the ``com.suse.bci`` prefix but ``com.suse.sle``.

"""
import json
from subprocess import check_output
from typing import Any
from typing import List
from typing import Union

import pytest
from _pytest.mark.structures import ParameterSet
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import ContainerT
from bci_tester.data import DOTNET_ASPNET_3_1_CONTAINER
from bci_tester.data import DOTNET_ASPNET_5_0_CONTAINER
from bci_tester.data import DOTNET_ASPNET_6_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_3_1_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_5_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_6_0_CONTAINER
from bci_tester.data import DOTNET_SDK_3_1_CONTAINER
from bci_tester.data import DOTNET_SDK_5_0_CONTAINER
from bci_tester.data import DOTNET_SDK_6_0_CONTAINER
from bci_tester.data import GO_1_16_CONTAINER
from bci_tester.data import GO_1_17_CONTAINER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import NODEJS_12_CONTAINER
from bci_tester.data import NODEJS_14_CONTAINER
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import PYTHON39_CONTAINER
from pytest_container import Container
from pytest_container import DerivedContainer
from pytest_container import OciRuntimeBase
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import LOCALHOST


#: The official vendor name
VENDOR = "SUSE LLC"

#: URL to the product's home page
URL = "https://www.suse.com/products/server/"


#: List of all containers and their respective names which are used in the image
#: labels ``com.suse.bci.$name``.
IMAGES_AND_NAMES: List[ParameterSet] = [
    pytest.param(
        cont,
        name,
        marks=()
        if isinstance(cont, (Container, DerivedContainer))
        else cont.marks,
    )
    for cont, name in (
        (BASE_CONTAINER, "base"),
        (MINIMAL_CONTAINER, "minimal"),
        (MICRO_CONTAINER, "micro"),
        (GO_1_16_CONTAINER, "golang"),
        (GO_1_17_CONTAINER, "golang"),
        (OPENJDK_11_CONTAINER, "openjdk"),
        (OPENJDK_DEVEL_11_CONTAINER, "openjdk.devel"),
        (NODEJS_12_CONTAINER, "nodejs"),
        (NODEJS_14_CONTAINER, "nodejs"),
        (PYTHON36_CONTAINER, "python"),
        (PYTHON39_CONTAINER, "python"),
        (INIT_CONTAINER, "init"),
        (DOTNET_SDK_3_1_CONTAINER, "dotnet.sdk"),
        (DOTNET_SDK_5_0_CONTAINER, "dotnet.sdk"),
        (DOTNET_SDK_6_0_CONTAINER, "dotnet.sdk"),
        (DOTNET_ASPNET_3_1_CONTAINER, "dotnet.aspnet"),
        (DOTNET_ASPNET_5_0_CONTAINER, "dotnet.aspnet"),
        (DOTNET_ASPNET_6_0_CONTAINER, "dotnet.aspnet"),
        (DOTNET_RUNTIME_3_1_CONTAINER, "dotnet.runtime"),
        (DOTNET_RUNTIME_5_0_CONTAINER, "dotnet.runtime"),
        (DOTNET_RUNTIME_6_0_CONTAINER, "dotnet.runtime"),
    )
]

assert len(ALL_CONTAINERS) == len(
    IMAGES_AND_NAMES
), "IMAGES_AND_NAMES must have all containers from BASE_CONTAINERS"


def get_container_metadata(container_data: ContainerT) -> Any:
    """Helper function that fetches the container metadata via :command:`skopeo
    inspect` of the container's base image.

    """
    return json.loads(
        check_output(
            [
                "skopeo",
                "inspect",
                f"docker://{container_from_pytest_param(container_data).get_base().url}",
            ],
        )
        .decode()
        .strip()
    )


@pytest.mark.parametrize(
    "container_data,container_name",
    [param for param in IMAGES_AND_NAMES if param.values[0] != BASE_CONTAINER]
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
    container_data: ContainerT,
    container_name: str,
):
    """Base check of the labels ``com.suse.bci.$name.$label`` and
    ``org.opencontainers.image.$label``:

    - ensure that ``BCI`` is in ``$label=title``
    - check that :py:const:`OS_PRETTY_NAME` is in ``$label=description``
    - ``$label=version`` is either ``latest`` or :py:const:`OS_VERSION`
    - ``$label=url`` equals :py:const:`URL`
    - ``$label=vendor`` equals :py:const:`VENDOR`
    """
    metadata = get_container_metadata(container_data)

    assert (
        metadata["Name"]
        == container_from_pytest_param(container_data)
        .get_base()
        .url.split(":")[0]
    )

    labels = metadata["Labels"]
    version = (
        container_from_pytest_param(container_data)
        .get_base()
        .url.split(":")[-1]
    )

    for prefix in (
        f"com.suse.bci.{container_name}",
        "org.opencontainers.image",
    ):
        assert "BCI" in labels[f"{prefix}.title"]
        assert ("Image containing" in labels[f"{prefix}.description"]) and (
            "based on the SLE Base Container Image."
            in labels[f"{prefix}.description"]
        )

        if version == "latest":
            assert OS_VERSION in labels[f"{prefix}.version"]
        else:
            version == labels[f"{prefix}.version"]
        assert labels[f"{prefix}.url"] == URL
        assert labels[f"{prefix}.vendor"] == VENDOR


@pytest.mark.parametrize(
    "container_data,container_name",
    [param for param in IMAGES_AND_NAMES if param.values[0] != BASE_CONTAINER]
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
    container_data: ContainerT,
    container_name: str,
):
    """General check of the ``org.openbuildservice.disturl`` label:

    verify that it exists, that it includes
    ``obs://build.suse.de/SUSE:SLE-15-SP3:Update`` and equals
    ``com.suse.bci.$name.disturl``.

    """
    labels = get_container_metadata(container_data)["Labels"]

    disturl = labels["org.openbuildservice.disturl"]

    assert disturl == labels[f"com.suse.bci.{container_name}.disturl"]
    assert "obs://build.suse.de/SUSE:SLE-15-SP3:Update" in disturl


@pytest.mark.skipif(
    not LOCALHOST.exists("osc"),
    reason="osc needs to be installed for this test",
)
@pytest.mark.parametrize("container_data", ALL_CONTAINERS)
def test_disturl_can_be_checked_out(
    container_data: ContainerT,
    tmp_path,
):
    """The Open Build Service automatically adds a ``org.openbuildservice.disturl``
    label that can be checked out using :command:`osc` to get the sources at
    exactly the version from which the container was build. This test verifies
    that it is possible to checkout this url. No further verification is run
    though, i.e. it could be potentially a completely different package.

    This test is skipped if :command:`osc` not installed. The test will fail
    when `<https://build.suse.de>`_ is unreachable.

    """
    labels = get_container_metadata(container_data)["Labels"]

    disturl = labels["org.openbuildservice.disturl"]
    check_output(["osc", "co", disturl], cwd=tmp_path)


@pytest.mark.parametrize(
    "container_data",
    [cont for cont in ALL_CONTAINERS if cont != BASE_CONTAINER],
)
def test_techpreview_label(
    container_data: ContainerT,
):
    """Check that all containers (except for the base container) have the label
    ``com.suse.techpreview`` set to ``1``.

    """
    metadata = get_container_metadata(container_data)
    assert (
        metadata["Labels"]["com.suse.techpreview"] == "1"
    ), "images must be marked as techpreview"


@pytest.mark.parametrize(
    "container_data,container_name",
    [param for param in IMAGES_AND_NAMES if param.values[0] != BASE_CONTAINER]
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
    container_data: ContainerT,
    container_name: str,
    container_runtime: OciRuntimeBase,
):
    """The ``reference`` label (available via ``org.opensuse.reference`` and
    ``com.suse.bci.$name.reference``) is a url that can be pulled via
    :command:`podman` or :command:`docker`.

    We check that both values are equal, that the container name is correct in
    the reference and that the reference begins with ``registry.suse.com/bci/``.

    """
    labels = get_container_metadata(container_data)["Labels"]

    reference = labels["org.opensuse.reference"]
    assert labels[f"com.suse.bci.{container_name}.reference"] == reference
    assert container_name.replace(".", "-") in reference

    assert reference[:22] == "registry.suse.com/bci/"

    # for the OS versioned containers we'll get a reference that contains the
    # current full version + release, which has not yet been published to the
    # registry (obviously). So instead we just try to fetch the current major
    # version of the OS for this container
    name, ver = reference.split(":")
    check_output(
        [
            container_runtime.runner_binary,
            "pull",
            reference if OS_VERSION != ver[:4] else f"{name}:{OS_VERSION}",
        ]
    )
