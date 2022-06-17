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
import enum
import json
from subprocess import check_output
from typing import Any
from typing import List

import pytest
from _pytest.mark.structures import ParameterSet
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINER_389DS
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
from bci_tester.data import GO_1_18_CONTAINER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import NODEJS_12_CONTAINER
from bci_tester.data import NODEJS_14_CONTAINER
from bci_tester.data import NODEJS_16_CONTAINER
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_17_CONTAINER
from bci_tester.data import OS_SP_VERSION
from bci_tester.data import OS_VERSION
from bci_tester.data import PCP_CONTAINER
from bci_tester.data import PYTHON310_CONTAINER
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import PYTHON39_CONTAINER
from bci_tester.data import RUBY_25_CONTAINER
from pytest_container import OciRuntimeBase
from pytest_container.container import container_from_pytest_param
from pytest_container.runtime import LOCALHOST


#: The official vendor name
VENDOR = "SUSE LLC"

#: URL to the product's home page
URL = "https://www.suse.com/products/server/"


@enum.unique
class ImageType(enum.Enum):
    """BCI type enumeration defining to which BCI class this container image
    belongs. It primarily influences whether the image specific labels appear as
    ``com.suse.bci`` or ``com.suse.application``.

    """

    LANGUAGE_STACK = enum.auto()
    APPLICATION = enum.auto()
    OS = enum.auto()

    def __str__(self) -> str:
        return (
            "application"
            if self.value == ImageType.APPLICATION.value
            else "bci"
        )


def _get_container_label_prefix(
    container_name: str, container_type: ImageType
) -> str:
    return f"com.suse.{container_type}.{container_name}"


#: List of all containers and their respective names which are used in the image
#: labels ``com.suse.bci.$name``.
IMAGES_AND_NAMES: List[ParameterSet] = [
    pytest.param(cont, name, img_type, marks=cont.marks)
    for cont, name, img_type in (
        (BASE_CONTAINER, "base", ImageType.OS),
        (MINIMAL_CONTAINER, "minimal", ImageType.OS),
        (MICRO_CONTAINER, "micro", ImageType.OS),
        (BUSYBOX_CONTAINER, "busybox", ImageType.OS),
        (GO_1_16_CONTAINER, "golang", ImageType.LANGUAGE_STACK),
        (GO_1_17_CONTAINER, "golang", ImageType.LANGUAGE_STACK),
        (GO_1_18_CONTAINER, "golang", ImageType.LANGUAGE_STACK),
        (OPENJDK_11_CONTAINER, "openjdk", ImageType.LANGUAGE_STACK),
        (
            OPENJDK_DEVEL_11_CONTAINER,
            "openjdk.devel",
            ImageType.LANGUAGE_STACK,
        ),
        (OPENJDK_17_CONTAINER, "openjdk", ImageType.LANGUAGE_STACK),
        (
            OPENJDK_DEVEL_17_CONTAINER,
            "openjdk.devel",
            ImageType.LANGUAGE_STACK,
        ),
        (NODEJS_12_CONTAINER, "nodejs", ImageType.LANGUAGE_STACK),
        (NODEJS_14_CONTAINER, "nodejs", ImageType.LANGUAGE_STACK),
        (NODEJS_16_CONTAINER, "nodejs", ImageType.LANGUAGE_STACK),
        (PYTHON36_CONTAINER, "python", ImageType.LANGUAGE_STACK),
        (PYTHON39_CONTAINER, "python", ImageType.LANGUAGE_STACK),
        (PYTHON310_CONTAINER, "python", ImageType.LANGUAGE_STACK),
        (RUBY_25_CONTAINER, "ruby", ImageType.LANGUAGE_STACK),
        (INIT_CONTAINER, "init", ImageType.OS),
        (PCP_CONTAINER, "pcp", ImageType.APPLICATION),
        (CONTAINER_389DS, "389-ds", ImageType.APPLICATION),
        (DOTNET_SDK_3_1_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
        (DOTNET_SDK_5_0_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
        (DOTNET_SDK_6_0_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
        (
            DOTNET_ASPNET_3_1_CONTAINER,
            "dotnet.aspnet",
            ImageType.LANGUAGE_STACK,
        ),
        (
            DOTNET_ASPNET_5_0_CONTAINER,
            "dotnet.aspnet",
            ImageType.LANGUAGE_STACK,
        ),
        (
            DOTNET_ASPNET_6_0_CONTAINER,
            "dotnet.aspnet",
            ImageType.LANGUAGE_STACK,
        ),
        (
            DOTNET_RUNTIME_3_1_CONTAINER,
            "dotnet.runtime",
            ImageType.LANGUAGE_STACK,
        ),
        (
            DOTNET_RUNTIME_5_0_CONTAINER,
            "dotnet.runtime",
            ImageType.LANGUAGE_STACK,
        ),
        (
            DOTNET_RUNTIME_6_0_CONTAINER,
            "dotnet.runtime",
            ImageType.LANGUAGE_STACK,
        ),
    )
]

IMAGES_AND_NAMES_WITH_BASE_XFAIL = [
    pytest.param(
        *IMAGES_AND_NAMES[0],
        marks=(
            pytest.mark.xfail(
                reason=(
                    "The base container has no com.suse.bci.base labels yet"
                    if OS_VERSION == "15.3"
                    else "https://bugzilla.suse.com/show_bug.cgi?id=1200373"
                )
            )
        ),
    )
] + IMAGES_AND_NAMES[1:]


assert len(ALL_CONTAINERS) == len(
    IMAGES_AND_NAMES
), "IMAGES_AND_NAMES must have all containers from BASE_CONTAINERS"


def get_container_metadata(container_data: ParameterSet) -> Any:
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
    "container_data,container_name,container_type",
    IMAGES_AND_NAMES_WITH_BASE_XFAIL,
)
def test_general_labels(
    container_data: ParameterSet,
    container_name: str,
    container_type: ImageType,
):
    """Base check of the labels ``com.suse.bci.$name.$label`` (for language
    stack containers and OS containers) or ``com.suse.application.$name.$label``
    (for application stack containers) and ``org.opencontainers.image.$label``:

    - ensure that ``BCI`` is in ``$label=title``
    - check that ``based on the SLE Base Container Image`` is in
      ``$label=description``
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
        _get_container_label_prefix(container_name, container_type),
        "org.opencontainers.image",
    ):
        if container_type != ImageType.APPLICATION:
            assert "BCI" in labels[f"{prefix}.title"]

        assert (
            "based on the SLE Base Container Image."
            in labels[f"{prefix}.description"]
        )

        if version == "latest":
            assert OS_VERSION in labels[f"{prefix}.version"]
        assert labels[f"{prefix}.url"] == URL
        assert labels[f"{prefix}.vendor"] == VENDOR

    assert labels["com.suse.lifecycle-url"] in (
        "https://www.suse.com/lifecycle",
        "https://www.suse.com/lifecycle/",
    )
    assert labels["com.suse.eula"] == "sle-bci"


@pytest.mark.parametrize(
    "container_data,container_name,container_type",
    IMAGES_AND_NAMES_WITH_BASE_XFAIL,
)
def test_disturl(
    container_data: ParameterSet,
    container_name: str,
    container_type: ImageType,
):
    """General check of the ``org.openbuildservice.disturl`` label:

    verify that it exists, that it includes
    ``obs://build.suse.de/SUSE:SLE-15-SP3:Update`` or
    ``obs://build.opensuse.org/devel:BCI:SLE-15-SP3`` and equals
    ``com.suse.bci.$name.disturl``.

    """
    labels = get_container_metadata(container_data)["Labels"]

    disturl = labels["org.openbuildservice.disturl"]
    assert (
        disturl
        == labels[
            f"{_get_container_label_prefix(container_name, container_type)}.disturl"
        ]
    )

    if (
        "opensuse.org"
        in container_from_pytest_param(container_data).get_base().url
    ):
        assert (
            f"obs://build.opensuse.org/devel:BCI:SLE-15-SP{OS_SP_VERSION}"
            in disturl
        )
    else:
        assert (
            f"obs://build.suse.de/SUSE:SLE-15-SP{OS_SP_VERSION}:Update"
            in disturl
        )


@pytest.mark.skipif(
    not LOCALHOST.exists("osc"),
    reason="osc needs to be installed for this test",
)
@pytest.mark.parametrize("container_data", ALL_CONTAINERS)
def test_disturl_can_be_checked_out(
    container_data: ParameterSet,
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
    "container_data,container_type",
    [
        pytest.param(param.values[0], param.values[2], marks=param.marks)
        for param in IMAGES_AND_NAMES
    ],
)
def test_image_type_label(
    container_data: ParameterSet,
    container_type: ImageType,
):
    """Check that all non-application containers have the label
    ``com.suse.image-type`` set to ``sle-bci`` and that all application
    containers have it set to ``application``.

    """
    metadata = get_container_metadata(container_data)
    if container_type == ImageType.APPLICATION:
        assert (
            metadata["Labels"]["com.suse.image-type"] == "application"
        ), "application container images must be marked as such"
    else:
        assert (
            metadata["Labels"]["com.suse.image-type"] == "sle-bci"
        ), "sle-bci images must be marked as such"


@pytest.mark.parametrize(
    "container_data",
    [cont for cont in ALL_CONTAINERS if cont != BASE_CONTAINER],
)
def test_supportlevel_label(
    container_data: ParameterSet,
):
    """Check that all containers (except for the base container) have the label
    ``com.suse.supportlevel`` set to ``true``.

    """
    metadata = get_container_metadata(container_data)
    assert (
        metadata["Labels"]["com.suse.supportlevel"] == "techpreview"
    ), "images must be marked as techpreview"


@pytest.mark.parametrize(
    "container_data,container_name,container_type",
    [
        param
        if param.values[0] != OPENJDK_DEVEL_17_CONTAINER
        else pytest.param(
            *param.values,
            marks=list(param.marks)
            + [
                pytest.mark.xfail(
                    reason="openjdk-devel:17 is not published on registry.suse.com"
                )
            ],
        )
        for param in IMAGES_AND_NAMES_WITH_BASE_XFAIL
    ],
)
def test_reference(
    container_data: ParameterSet,
    container_name: str,
    container_type: ImageType,
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
    assert (
        labels[
            f"{_get_container_label_prefix(container_name, container_type)}.reference"
        ]
        == reference
    )
    assert container_name.replace(".", "-") in reference

    if container_type == ImageType.APPLICATION:
        assert reference[:23] == "registry.suse.com/suse/"
    else:
        assert reference[:22] == "registry.suse.com/bci/"

    # for the OS versioned containers we'll get a reference that contains the
    # current full version + release, which has not yet been published to the
    # registry (obviously). So instead we just try to fetch the current major
    # version of the OS for this container
    name, version_release = reference.split(":")
    if container_type == ImageType.OS:
        ref = f"{name}:{OS_VERSION}"
    else:
        version, _ = version_release.split("-")
        ref = f"{name}:{version}"

    LOCALHOST.run_expect([0], f"{container_runtime.runner_binary} pull {ref}")
