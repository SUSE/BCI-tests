"""Verification of the container metadata that are available via the registry.

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
from subprocess import check_output
from typing import List

import pytest
from _pytest.mark.structures import ParameterSet
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import ACC_CONTAINERS
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINER_389DS_CONTAINERS
from bci_tester.data import DISTRIBUTION_CONTAINER
from bci_tester.data import DOTNET_ASPNET_6_0_CONTAINER
from bci_tester.data import DOTNET_ASPNET_7_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_6_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_7_0_CONTAINER
from bci_tester.data import DOTNET_SDK_6_0_CONTAINER
from bci_tester.data import DOTNET_SDK_7_0_CONTAINER
from bci_tester.data import GIT_CONTAINER
from bci_tester.data import GOLANG_CONTAINERS
from bci_tester.data import HELM_CONTAINER
from bci_tester.data import ImageType
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import L3_CONTAINERS
from bci_tester.data import LTSS_BASE_CONTAINERS
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import NGINX_CONTAINER
from bci_tester.data import NODEJS_18_CONTAINER
from bci_tester.data import NODEJS_20_CONTAINER
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER
from bci_tester.data import OPENJDK_21_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_17_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_21_CONTAINER
from bci_tester.data import OS_SP_VERSION
from bci_tester.data import OS_VERSION
from bci_tester.data import PCP_CONTAINER
from bci_tester.data import PHP_8_APACHE
from bci_tester.data import PHP_8_CLI
from bci_tester.data import PHP_8_FPM
from bci_tester.data import POSTGRESQL_CONTAINERS
from bci_tester.data import PYTHON310_CONTAINER
from bci_tester.data import PYTHON311_CONTAINER
from bci_tester.data import PYTHON36_CONTAINER
from bci_tester.data import RUBY_25_CONTAINER
from bci_tester.data import RUBY_32_CONTAINER
from bci_tester.data import RUST_CONTAINERS


#: The official vendor name
VENDOR = "openSUSE Project" if OS_VERSION == "tumbleweed" else "SUSE LLC"

#: URL to the product's home page
URL = (
    "https://www.opensuse.org"
    if OS_VERSION == "tumbleweed"
    else "https://www.suse.com/products/server/"
)


SKIP_IF_TW_MARK = pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="no supportlevel labels on openSUSE containers",
)


def _get_container_label_prefix(
    container_name: str, container_type: ImageType
) -> str:
    if OS_VERSION == "tumbleweed":
        return f"org.opensuse.{container_type}.{container_name}"
    if container_type == ImageType.OS_LTSS:
        return f"com.suse.sle.{container_name}"
    return f"com.suse.{container_type}.{container_name}"


#: List of all containers and their respective names which are used in the image
#: labels ``com.suse.bci.$name``.
IMAGES_AND_NAMES: List[ParameterSet] = [
    pytest.param(cont, name, img_type, marks=cont.marks)
    for cont, name, img_type in [
        # containers with XFAILs below
        (BASE_CONTAINER, "base", ImageType.OS),
        (GIT_CONTAINER, "git", ImageType.APPLICATION),
        (HELM_CONTAINER, "helm", ImageType.APPLICATION),
    ]
    # all other containers
    + [
        (MINIMAL_CONTAINER, "minimal", ImageType.OS),
        (MICRO_CONTAINER, "micro", ImageType.OS),
        (BUSYBOX_CONTAINER, "busybox", ImageType.OS),
        (KERNEL_MODULE_CONTAINER, "sle15-kernel-module-devel", ImageType.OS),
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
        (OPENJDK_21_CONTAINER, "openjdk", ImageType.LANGUAGE_STACK),
        (
            OPENJDK_DEVEL_21_CONTAINER,
            "openjdk.devel",
            ImageType.LANGUAGE_STACK,
        ),
        (NODEJS_18_CONTAINER, "nodejs", ImageType.LANGUAGE_STACK),
        (NODEJS_20_CONTAINER, "nodejs", ImageType.LANGUAGE_STACK),
        (PYTHON36_CONTAINER, "python", ImageType.LANGUAGE_STACK),
        (PYTHON310_CONTAINER, "python", ImageType.LANGUAGE_STACK),
        (PYTHON311_CONTAINER, "python", ImageType.LANGUAGE_STACK),
        (RUBY_25_CONTAINER, "ruby", ImageType.LANGUAGE_STACK),
        (RUBY_32_CONTAINER, "ruby", ImageType.LANGUAGE_STACK),
        (INIT_CONTAINER, "init", ImageType.OS),
        (PHP_8_APACHE, "php-apache", ImageType.LANGUAGE_STACK),
        (PHP_8_CLI, "php", ImageType.LANGUAGE_STACK),
        (PHP_8_FPM, "php-fpm", ImageType.LANGUAGE_STACK),
        (PCP_CONTAINER, "pcp", ImageType.APPLICATION),
        (NGINX_CONTAINER, "nginx", ImageType.APPLICATION),
    ]
    + [
        (container_389ds, "389-ds", ImageType.APPLICATION)
        for container_389ds in CONTAINER_389DS_CONTAINERS
    ]
    + [
        (rust_container, "rust", ImageType.LANGUAGE_STACK)
        for rust_container in RUST_CONTAINERS
    ]
    + [
        (golang_container, "golang", ImageType.LANGUAGE_STACK)
        for golang_container in GOLANG_CONTAINERS
    ]
    + [
        (pg_container, "postgres", ImageType.APPLICATION)
        for pg_container in POSTGRESQL_CONTAINERS
    ]
    + [
        (DISTRIBUTION_CONTAINER, "registry", ImageType.APPLICATION),
    ]
    + (
        [
            (DOTNET_SDK_6_0_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
            (DOTNET_SDK_7_0_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
            (
                DOTNET_ASPNET_6_0_CONTAINER,
                "dotnet.aspnet",
                ImageType.LANGUAGE_STACK,
            ),
            (
                DOTNET_ASPNET_7_0_CONTAINER,
                "dotnet.aspnet",
                ImageType.LANGUAGE_STACK,
            ),
            (
                DOTNET_RUNTIME_6_0_CONTAINER,
                "dotnet.runtime",
                ImageType.LANGUAGE_STACK,
            ),
            (
                DOTNET_RUNTIME_7_0_CONTAINER,
                "dotnet.runtime",
                ImageType.LANGUAGE_STACK,
            ),
        ]
        if LOCALHOST.system_info.arch == "x86_64"
        else []
    )
    + [(cont, "base", ImageType.OS_LTSS) for cont in LTSS_BASE_CONTAINERS]
    + [
        (cont, "base-fips", ImageType.OS_LTSS)
        for cont in LTSS_BASE_FIPS_CONTAINERS
    ]
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
    ),
] + IMAGES_AND_NAMES[1:]

assert len(ALL_CONTAINERS) == len(
    IMAGES_AND_NAMES
), "IMAGES_AND_NAMES must have all containers from ALL_CONTAINERS"


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES_WITH_BASE_XFAIL,
    indirect=["container"],
)
def test_general_labels(
    container: ContainerData,
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

    labels = container.inspect.config.labels
    version = container.container.get_base().url.split(":")[-1]

    for prefix in (
        _get_container_label_prefix(container_name, container_type),
        "org.opencontainers.image",
    ):
        if container_type not in (ImageType.APPLICATION, ImageType.OS_LTSS):
            assert "BCI" in labels[f"{prefix}.title"]

        if OS_VERSION == "tumbleweed":
            assert (
                "based on the openSUSE Tumbleweed Base Container Image."
                in labels[f"{prefix}.description"]
            )
        elif container_type == ImageType.OS_LTSS:
            assert (
                "based on SUSE Linux Enterprise Server 15"
                in labels[f"{prefix}.description"]
            )
        else:
            assert (
                "based on the SLE Base Container Image."
                in labels[f"{prefix}.description"]
            )

        if version == "tumbleweed":
            assert OS_VERSION in labels[f"{prefix}.version"]
        assert labels[f"{prefix}.url"] == URL
        assert labels[f"{prefix}.vendor"] == VENDOR

    if OS_VERSION == "tumbleweed":
        assert labels["org.opensuse.lifecycle-url"] in (
            "https://en.opensuse.org/Lifetime",
        )
        # no EULA for openSUSE images
    else:
        assert labels["com.suse.lifecycle-url"] in (
            "https://www.suse.com/lifecycle#suse-linux-enterprise-server-15",
            "https://www.suse.com/lifecycle",
        )
        if container_type == ImageType.OS_LTSS:
            assert labels["com.suse.eula"] == "sle-eula"
        else:
            assert labels["com.suse.eula"] == "sle-bci"


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES_WITH_BASE_XFAIL,
    indirect=["container"],
)
def test_disturl(
    container: ContainerData,
    container_name: str,
    container_type: ImageType,
):
    """General check of the ``org.openbuildservice.disturl`` label:

    verify that it exists, that it includes
    ``obs://build.suse.de/SUSE:SLE-15-SP3:Update`` or
    ``obs://build.opensuse.org/devel:BCI:SLE-15-SP3`` and equals
    ``com.suse.bci.$name.disturl``.

    """
    labels = container.inspect.config.labels

    disturl = labels["org.openbuildservice.disturl"]
    assert (
        disturl
        == labels[
            f"{_get_container_label_prefix(container_name, container_type)}.disturl"
        ]
    )

    if OS_VERSION == "tumbleweed":
        assert "obs://build.opensuse.org/devel:BCI:Tumbleweed" in disturl
    else:
        if "opensuse.org" in container.container.get_base().url:
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
@pytest.mark.parametrize("container", ALL_CONTAINERS, indirect=True)
def test_disturl_can_be_checked_out(
    container: ContainerData,
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
    disturl = container.inspect.config.labels["org.openbuildservice.disturl"]
    check_output(["osc", "co", disturl], cwd=tmp_path)


@SKIP_IF_TW_MARK
@pytest.mark.parametrize(
    "container,container_type",
    [
        pytest.param(param.values[0], param.values[2], marks=param.marks)
        for param in IMAGES_AND_NAMES
    ],
    indirect=["container"],
)
def test_image_type_label(
    container: ContainerData,
    container_type: ImageType,
):
    """Check that all non-application containers have the label
    ``com.suse.image-type`` set to ``sle-bci`` and that all application
    containers have it set to ``application``.

    """
    labels = container.inspect.config.labels
    if container_type == ImageType.APPLICATION:
        assert (
            labels["com.suse.image-type"] == "application"
        ), "application container images must be marked as such"
    else:
        assert (
            labels["com.suse.image-type"] == "sle-bci"
        ), "sle-bci images must be marked as such"


@SKIP_IF_TW_MARK
@pytest.mark.parametrize(
    "container",
    [
        cont
        for cont in ALL_CONTAINERS
        if cont not in L3_CONTAINERS and cont not in ACC_CONTAINERS
    ],
    indirect=True,
)
def test_techpreview_label(container: ContainerData):
    """Check that containers that are not L3 supported have the label
    ``com.suse.supportlevel`` set to ``techpreview``.
    Reference: https://confluence.suse.com/display/ENGCTNRSTORY/SLE+BCI+Image+Overview
    """
    assert (
        container.inspect.config.labels["com.suse.supportlevel"]
        == "techpreview"
    ), "images must be marked as techpreview"


@SKIP_IF_TW_MARK
@pytest.mark.parametrize(
    "container",
    list(ACC_CONTAINERS),
    indirect=True,
)
def test_acc_label(container: ContainerData):
    """Check that containers that are in ACC_CONTAINERS have
    ``com.suse.supportlevel`` set to ``acc``.
    Reference: https://confluence.suse.com/display/ENGCTNRSTORY/SLE+BCI+Image+Overview
    """
    assert (
        container.inspect.config.labels["com.suse.supportlevel"] == "acc"
    ), "acc images must be marked as acc"


@SKIP_IF_TW_MARK
@pytest.mark.parametrize("container", L3_CONTAINERS, indirect=True)
def test_l3_label(container: ContainerData):
    """Check that containers under L3 support have the label
    ``com.suse.supportlevel`` set to ``l3``.
    Reference: https://confluence.suse.com/display/ENGCTNRSTORY/SLE+BCI+Image+Overview
    """
    assert (
        container.inspect.config.labels["com.suse.supportlevel"] == "l3"
    ), "image supportlevel must be marked as L3"


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES_WITH_BASE_XFAIL,
    indirect=["container"],
)
def test_reference(
    container: ContainerData,
    container_name: str,
    container_type: ImageType,
    container_runtime: OciRuntimeBase,
):
    """The ``reference`` label (available via ``org.opensuse.reference`` and
    ``com.suse.bci.$name.reference``) is pointing to a manifest that can be
    inspected via :command:`podman` or :command:`docker`.

    We check that both values are equal, that the container name is correct in
    the reference and that the reference begins with the expected registry url.

    """
    labels = container.inspect.config.labels

    reference = labels["org.opensuse.reference"]
    assert (
        labels[
            f"{_get_container_label_prefix(container_name, container_type)}.reference"
        ]
        == reference
    )
    if container_type != ImageType.OS_LTSS:
        assert container_name.replace(".", "-") in reference

    if OS_VERSION == "tumbleweed":
        if container_type == ImageType.APPLICATION:
            assert reference.startswith("registry.opensuse.org/opensuse/")
        else:
            assert reference.startswith("registry.opensuse.org/opensuse/bci/")
    else:
        if container_type == ImageType.APPLICATION:
            assert reference.startswith("registry.suse.com/suse/")
        elif container_type == ImageType.OS_LTSS:
            assert reference.startswith("registry.suse.com/suse/ltss/sle15")
        else:
            assert reference.startswith("registry.suse.com/bci/")

    # for the OS versioned containers we'll get a reference that contains the
    # current full version + release, which has not yet been published to the
    # registry (obviously). So instead we just try to fetch the current major
    # version of the OS for this container
    name, version_release = reference.split(":")
    if container_type == ImageType.OS:
        ref = (
            f"{name}:latest"
            if OS_VERSION == "tumbleweed"
            else f"{name}:{OS_VERSION}"
        )
    else:
        version = list(version_release.split("-"))[0]
        ref = f"{name}:{version}"

    # only test if our testing target is released - otherwise we'll just fail on
    # containers that are not yet ever released
    if not container.container.baseurl.startswith(ref.partition(":")[0]):
        pytest.skip(
            f"reference {ref} not checked in TARGET={container.container.baseurl}"
        )

    LOCALHOST.run_expect(
        [0], f"{container_runtime.runner_binary} manifest inspect {ref}"
    )
