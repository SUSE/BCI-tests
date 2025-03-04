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

import urllib.parse
from pathlib import Path
from typing import List
from typing import Tuple

import pytest
import requests
from _pytest.mark.structures import ParameterSet
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import ACC_CONTAINERS
from bci_tester.data import ALERTMANAGER_CONTAINERS
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BASE_FIPS_CONTAINERS
from bci_tester.data import BLACKBOX_CONTAINERS
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINER_389DS_CONTAINERS
from bci_tester.data import COSIGN_CONTAINERS
from bci_tester.data import DISTRIBUTION_CONTAINER
from bci_tester.data import DOTNET_ASPNET_8_0_CONTAINER
from bci_tester.data import DOTNET_ASPNET_9_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_8_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_9_0_CONTAINER
from bci_tester.data import DOTNET_SDK_8_0_CONTAINER
from bci_tester.data import DOTNET_SDK_9_0_CONTAINER
from bci_tester.data import GCC_CONTAINERS
from bci_tester.data import GIT_CONTAINER
from bci_tester.data import GOLANG_CONTAINERS
from bci_tester.data import GRAFANA_CONTAINERS
from bci_tester.data import HELM_CONTAINER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import KEA_CONTAINERS
from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import KIWI_CONTAINERS
from bci_tester.data import KUBECTL_CONTAINERS
from bci_tester.data import L3_CONTAINERS
from bci_tester.data import LTSS_BASE_CONTAINERS
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import MARIADB_CLIENT_CONTAINERS
from bci_tester.data import MARIADB_CONTAINERS
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MILVUS_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import NGINX_CONTAINER
from bci_tester.data import NODEJS_CONTAINERS
from bci_tester.data import OLLAMA_CONTAINER
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER
from bci_tester.data import OPENJDK_21_CONTAINER
from bci_tester.data import OPENJDK_23_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_17_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_21_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_23_CONTAINER
from bci_tester.data import OPENWEBUI_CONTAINER
from bci_tester.data import OS_SP_VERSION
from bci_tester.data import OS_VERSION
from bci_tester.data import OS_VERSION_ID
from bci_tester.data import PCP_CONTAINERS
from bci_tester.data import PHP_8_APACHE
from bci_tester.data import PHP_8_CLI
from bci_tester.data import PHP_8_FPM
from bci_tester.data import POSTFIX_CONTAINERS
from bci_tester.data import POSTGRESQL_CONTAINERS
from bci_tester.data import PROMETHEUS_CONTAINERS
from bci_tester.data import PYTHON_CONTAINERS
from bci_tester.data import PYTORCH_CONTAINER
from bci_tester.data import RUBY_CONTAINERS
from bci_tester.data import RUST_CONTAINERS
from bci_tester.data import SAC_PYTHON_CONTAINERS
from bci_tester.data import SPACK_CONTAINERS
from bci_tester.data import STUNNEL_CONTAINER
from bci_tester.data import TOMCAT_CONTAINERS
from bci_tester.data import ImageType
from bci_tester.runtime_choice import PODMAN_SELECTED

#: The official vendor name
VENDOR = "openSUSE Project" if OS_VERSION == "tumbleweed" else "SUSE LLC"

SKIP_IF_TW_MARK = pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="no supportlevel labels on openSUSE containers",
)


def _get_container_label_prefix(
    container_name: str, container_type: ImageType
) -> str:
    if OS_VERSION == "tumbleweed" and container_name == "base":
        return "org.opensuse.base"
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
        (BASE_CONTAINER, "base", ImageType.OS),
        (GIT_CONTAINER, "git", ImageType.APPLICATION),
        (HELM_CONTAINER, "helm", ImageType.APPLICATION),
        (MINIMAL_CONTAINER, "minimal", ImageType.OS),
        (MICRO_CONTAINER, "micro", ImageType.OS),
        (BUSYBOX_CONTAINER, "busybox", ImageType.OS),
        (
            KERNEL_MODULE_CONTAINER,
            (
                "sle16-kernel-module-devel"
                if OS_VERSION.startswith("16")
                else "sle15-kernel-module-devel"
            ),
            ImageType.OS,
        ),
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
        (OPENJDK_23_CONTAINER, "openjdk", ImageType.LANGUAGE_STACK),
        (
            OPENJDK_DEVEL_23_CONTAINER,
            "openjdk.devel",
            ImageType.LANGUAGE_STACK,
        ),
        (INIT_CONTAINER, "init", ImageType.OS),
        (PHP_8_APACHE, "php-apache", ImageType.LANGUAGE_STACK),
        (PHP_8_CLI, "php", ImageType.LANGUAGE_STACK),
        (PHP_8_FPM, "php-fpm", ImageType.LANGUAGE_STACK),
        (NGINX_CONTAINER, "nginx", ImageType.APPLICATION),
    ]
    + [(c, "nodejs", ImageType.LANGUAGE_STACK) for c in NODEJS_CONTAINERS]
    + [(c, "python", ImageType.LANGUAGE_STACK) for c in PYTHON_CONTAINERS]
    + [(c, "ruby", ImageType.LANGUAGE_STACK) for c in RUBY_CONTAINERS]
    + [
        (c, "python", ImageType.SAC_LANGUAGE_STACK)
        for c in SAC_PYTHON_CONTAINERS
    ]
    + [(c, "base-fips", ImageType.OS) for c in BASE_FIPS_CONTAINERS]
    + [
        (container_pcp, "pcp", ImageType.APPLICATION)
        for container_pcp in PCP_CONTAINERS
    ]
    + [(kiwi, "kiwi", ImageType.LANGUAGE_STACK) for kiwi in KIWI_CONTAINERS]
    + [
        (tomcat_ctr, "apache-tomcat", ImageType.SAC_APPLICATION)
        for tomcat_ctr in TOMCAT_CONTAINERS
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
        (cosign_container, "cosign", ImageType.APPLICATION)
        for cosign_container in COSIGN_CONTAINERS
    ]
    + [
        (golang_container, "golang", ImageType.LANGUAGE_STACK)
        for golang_container in GOLANG_CONTAINERS
    ]
    + [
        (spack_container, "spack", ImageType.LANGUAGE_STACK)
        for spack_container in SPACK_CONTAINERS
    ]
    + [
        (gcc_container, "gcc", ImageType.LANGUAGE_STACK)
        for gcc_container in GCC_CONTAINERS
    ]
    + [
        (mariab_container, "mariadb", ImageType.APPLICATION)
        for mariab_container in MARIADB_CONTAINERS
    ]
    + [
        (mariab_client_container, "mariadb-client", ImageType.APPLICATION)
        for mariab_client_container in MARIADB_CLIENT_CONTAINERS
    ]
    + [
        (postfix_container, "postfix", ImageType.SAC_APPLICATION)
        for postfix_container in POSTFIX_CONTAINERS
    ]
    + [
        (pg_container, "postgres", ImageType.APPLICATION)
        for pg_container in POSTGRESQL_CONTAINERS
    ]
    + [
        (prom_container, "prometheus", ImageType.APPLICATION)
        for prom_container in PROMETHEUS_CONTAINERS
    ]
    + [
        (alertmngr_ctr, "alertmanager", ImageType.APPLICATION)
        for alertmngr_ctr in ALERTMANAGER_CONTAINERS
    ]
    + [
        (blackbox_ctr, "blackbox_exporter", ImageType.APPLICATION)
        for blackbox_ctr in BLACKBOX_CONTAINERS
    ]
    + [
        (grafana_container, "grafana", ImageType.APPLICATION)
        for grafana_container in GRAFANA_CONTAINERS
    ]
    + [
        (DISTRIBUTION_CONTAINER, "registry", ImageType.APPLICATION),
    ]
    + (
        [
            (DOTNET_SDK_8_0_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
            (DOTNET_SDK_9_0_CONTAINER, "dotnet.sdk", ImageType.LANGUAGE_STACK),
            (
                DOTNET_ASPNET_8_0_CONTAINER,
                "dotnet.aspnet",
                ImageType.LANGUAGE_STACK,
            ),
            (
                DOTNET_ASPNET_9_0_CONTAINER,
                "dotnet.aspnet",
                ImageType.LANGUAGE_STACK,
            ),
            (
                DOTNET_RUNTIME_8_0_CONTAINER,
                "dotnet.runtime",
                ImageType.LANGUAGE_STACK,
            ),
            (
                DOTNET_RUNTIME_9_0_CONTAINER,
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
    + [
        (OLLAMA_CONTAINER, "ollama", ImageType.SAC_APPLICATION),
        (OPENWEBUI_CONTAINER, "open-webui", ImageType.SAC_APPLICATION),
        (MILVUS_CONTAINER, "milvus", ImageType.SAC_APPLICATION),
        (PYTORCH_CONTAINER, "pytorch", ImageType.SAC_APPLICATION),
    ]
    + [(STUNNEL_CONTAINER, "stunnel", ImageType.APPLICATION)]
    + [
        (kubectl_container, "kubectl", ImageType.APPLICATION)
        for kubectl_container in KUBECTL_CONTAINERS
    ]
    + [
        (kea_container, "kea", ImageType.APPLICATION)
        for kea_container in KEA_CONTAINERS
    ]
]


assert len(ALL_CONTAINERS) == len(IMAGES_AND_NAMES), (
    "IMAGES_AND_NAMES must have all containers from ALL_CONTAINERS"
)


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES,
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
        if (
            container_name != "base"
            and container_type != ImageType.SAC_APPLICATION
        ):
            if OS_VERSION == "tumbleweed":
                assert (
                    "based on the openSUSE Tumbleweed Base Container Image."
                    in labels[f"{prefix}.description"]
                )
            elif container_type == ImageType.OS_LTSS:
                assert (
                    "based on SUSE Linux Enterprise Server 15"
                    in labels[f"{prefix}.description"]
                    or "based on the SLE LTSS Base Container Image"
                    in labels[f"{prefix}.description"]
                )
            else:
                assert (
                    "based on the SLE Base Container Image."
                    in labels[f"{prefix}.description"]
                )

        if version == "tumbleweed":
            assert OS_VERSION in labels[f"{prefix}.version"]

        expected_url: Tuple[str, ...] = (
            "https://www.suse.com/products/base-container-images/",
        ) + (
            ("https://www.suse.com/products/server/",)
            if container_name in ("base",)
            else ()
        )
        if OS_VERSION == "tumbleweed":
            expected_url = (
                "https://www.opensuse.org",
                "https://www.opensuse.org/",
            )
        elif container_type in (
            ImageType.SAC_LANGUAGE_STACK,
            ImageType.SAC_APPLICATION,
        ):
            expected_url = (
                f"https://apps.rancher.io/applications/{container_name}",
            )
        elif container_type == ImageType.OS_LTSS:
            expected_url = (
                "https://www.suse.com/products/long-term-service-pack-support/",
            )

        assert labels[f"{prefix}.url"] in expected_url, (
            f"expected LABEL {prefix}.url = {expected_url} but is {labels[f'{prefix}.url']}"
        )
        assert labels[f"{prefix}.vendor"] == VENDOR

    if OS_VERSION == "tumbleweed":
        assert (
            labels["org.opensuse.lifecycle-url"]
            in (
                "https://en.opensuse.org/Lifetime#openSUSE_BCI",
                "https://en.opensuse.org/Lifetime",  # Base container has incorrect URL
            )
        )
        # no EULA for openSUSE images
    else:
        assert (
            labels["com.suse.lifecycle-url"]
            in (
                "https://www.suse.com/lifecycle#suse-linux-enterprise-server-15",
                "https://www.suse.com/lifecycle",  # SLE 15 SP5 base container has incorrect URL
            )
        )
        if container_type in (
            ImageType.OS_LTSS,
            ImageType.APPLICATION,
            ImageType.SAC_LANGUAGE_STACK,
            ImageType.SAC_APPLICATION,
        ):
            assert labels["com.suse.eula"] == "sle-eula"
        else:
            assert labels["com.suse.eula"] == "sle-bci"
            assert "BCI" in labels[f"{prefix}.title"]


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES,
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
        assert any(
            (
                "obs://build.opensuse.org/devel:BCI:Tumbleweed" in disturl,
                "obs://build.opensuse.org/openSUSE:Factory" in disturl,
            )
        )
    elif OS_VERSION == "16.0":
        if "opensuse.org" in container.container.get_base().url:
            assert (
                f"obs://build.opensuse.org/devel:BCI:16.{OS_SP_VERSION}"
                in disturl
            )
        else:
            assert (
                f"obs://build.suse.de/SUSE:SLFO:Products:SLES:16.{OS_SP_VERSION}"
                in disturl
            )
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


@pytest.mark.parametrize("container", ALL_CONTAINERS, indirect=True)
def test_disturl_can_be_checked_out(
    container: ContainerData, pytestconfig: pytest.Config
):
    """The Open Build Service automatically adds a ``org.openbuildservice.disturl``
    label that can be checked out using :command:`osc` to get the sources at
    exactly the version from which the container was build. This test verifies
    that the url is accessible.
    """
    disturl_label = container.inspect.config.labels[
        "org.openbuildservice.disturl"
    ]
    disturl = urllib.parse.urlparse(disturl_label)

    assert disturl.scheme == "obs", f"unsupported scheme in {disturl_label}"
    for p in ("params", "query", "fragment"):
        assert getattr(disturl, p) == "", f"unsupported {p} in {disturl_label}"

    src_revision, _, src_package = Path(disturl.path).name.partition("-")
    src_package = src_package.partition(":")[0]  # strip multibuild flavor
    src_project = Path(disturl.path).parent.parent.name

    cert = (
        str(pytestconfig.rootpath / "tests" / "files" / "SUSE_Trust_Root.crt")
        if "suse.de" in disturl.hostname
        else None
    )
    try:
        req = requests.get(
            f"https://{disturl.hostname}/public/source/{src_project}/{src_package}",
            params={"rev": src_revision},
            cert=cert,
            timeout=(5, 10),
        )
    except requests.exceptions.ConnectionError as e:
        if "suse.de" in disturl.hostname:
            pytest.skip(reason=f"Cannot connect to SUSE internal host: {e}")
        raise
    req.raise_for_status()
    assert "kiwi" in req.text or "Dockerfile" in req.text, (
        "Cannot find a valid build description"
    )


@SKIP_IF_TW_MARK
@pytest.mark.parametrize(
    "container",
    [
        cont
        for cont in ALL_CONTAINERS
        if (
            cont not in L3_CONTAINERS
            and cont not in ACC_CONTAINERS
            and cont != BASE_CONTAINER
        )
    ]
    + [
        pytest.param(
            BASE_CONTAINER.values,
            marks=BASE_CONTAINER.marks
            + [
                pytest.mark.xfail(
                    reason="Base container for SLE 15 SP6 is not using the techpreview label (https://build.suse.de/request/show/325200)"
                )
            ],
        )
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
    assert container.inspect.config.labels["com.suse.supportlevel"] == "acc", (
        "acc images must be marked as acc"
    )


@SKIP_IF_TW_MARK
@pytest.mark.parametrize("container", L3_CONTAINERS, indirect=True)
def test_l3_label(container: ContainerData):
    """Check that containers under L3 support have the label
    ``com.suse.supportlevel`` set to ``l3``.
    Reference: https://confluence.suse.com/display/ENGCTNRSTORY/SLE+BCI+Image+Overview
    """
    assert container.inspect.config.labels["com.suse.supportlevel"] == "l3", (
        "image supportlevel must be marked as L3"
    )


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES,
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
        reference_name = container_name.replace(".", "-")
        # the BCI-base container is actually identifying itself as the os container
        # Fixed by creating bci-base from dockerfile-generator on 15.6+
        if OS_VERSION in ("15.5", "tumbleweed") and container_name in (
            "base",
        ):
            reference_name = "sle15" if OS_VERSION == "15.5" else "tumbleweed"
        assert reference_name in reference

    if OS_VERSION == "tumbleweed":
        if container_type in (
            ImageType.APPLICATION,
            ImageType.SAC_APPLICATION,
        ) or container_name in ("base",):
            assert reference.startswith("registry.opensuse.org/opensuse/")
        else:
            assert reference.startswith("registry.opensuse.org/opensuse/bci/")
    else:
        if container_type in (
            ImageType.SAC_LANGUAGE_STACK,
            ImageType.SAC_APPLICATION,
        ):
            assert reference.startswith("dp.apps.rancher.io/containers/")
        elif container_type == ImageType.APPLICATION or (
            OS_VERSION == "15.5" and container_name in ("base",)
        ):
            assert reference.startswith("registry.suse.com/suse/")
        elif container_type == ImageType.OS_LTSS:
            assert reference.startswith("registry.suse.com/suse/ltss/sle15")
        else:
            assert reference.startswith("registry.suse.com/bci/")

    # for the OS versioned containers we'll get a reference that contains the
    # current full version + release, which is unpublished in the public registry
    # at the time of testing. Hence we fetch the current major version of the OS
    # for this container and compare that.
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

    # Skip testing containers that have not yet been released to avoid unnecessary failures
    if not container.container.baseurl.startswith(ref.partition(":")[0]):
        pytest.skip(
            f"reference {ref} not checked in TARGET={container.container.baseurl}"
        )

    LOCALHOST.run_expect(
        [0], f"{container_runtime.runner_binary} manifest inspect {ref}"
    )


@SKIP_IF_TW_MARK
@pytest.mark.parametrize("container", ALL_CONTAINERS, indirect=True)
def test_oci_base_refs(
    container: ContainerData,
    container_runtime: OciRuntimeBase,
):
    """The ``org.opencontainers.image.base.digest`` label is pointing to a
    digest that can be inspected via :command:`podman` or :command:`docker`.
    """
    labels = container.inspect.config.labels

    if "org.opencontainers.image.base.digest" not in labels:
        pytest.skip("no oci base ref annotation set - itself a base image?")

    base_digest: str = labels["org.opencontainers.image.base.digest"]
    base_name: str = labels["org.opencontainers.image.base.name"]

    assert ":" in base_name, (
        f"`org.opencontainers.image.base.name` is not the expected format: {base_name}"
    )
    base_repository = base_name.partition(":")[0]

    assert base_name.startswith("registry.suse.com/")
    assert f":{OS_VERSION_ID}" in base_name, (
        "Base image reference is not the expected version"
    )
    assert base_digest.startswith("sha256:")

    if PODMAN_SELECTED and container_runtime.version.major < 3:
        pytest.skip("Podman version too old for checking manifest")

    LOCALHOST.check_output(
        f"{container_runtime.runner_binary} manifest inspect {base_repository}@{base_digest}",
    )
