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

import base64
import datetime
import json
import urllib.parse
from pathlib import Path
from typing import Any
from typing import List
from typing import Tuple

import pytest
import requests
from _pytest.mark.structures import ParameterSet
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import ACC_CONTAINERS
from bci_tester.data import ALERTMANAGER_CONTAINERS
from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BASE_FIPS_CONTAINERS
from bci_tester.data import BIND_CONTAINERS
from bci_tester.data import BLACKBOX_CONTAINERS
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINER_389DS_CONTAINERS
from bci_tester.data import COSIGN_CONTAINERS
from bci_tester.data import DISTRIBUTION_CONTAINER
from bci_tester.data import DOTNET_ASPNET_8_0_CONTAINER
from bci_tester.data import DOTNET_ASPNET_9_0_CONTAINER
from bci_tester.data import DOTNET_ASPNET_10_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_8_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_9_0_CONTAINER
from bci_tester.data import DOTNET_RUNTIME_10_0_CONTAINER
from bci_tester.data import DOTNET_SDK_8_0_CONTAINER
from bci_tester.data import DOTNET_SDK_9_0_CONTAINER
from bci_tester.data import DOTNET_SDK_10_0_CONTAINER
from bci_tester.data import GCC_CONTAINERS
from bci_tester.data import GIT_CONTAINER
from bci_tester.data import GOLANG_CONTAINERS
from bci_tester.data import GRAFANA_CONTAINERS
from bci_tester.data import HELM_CONTAINER
from bci_tester.data import INIT_CONTAINER
from bci_tester.data import KEA_CONTAINERS
from bci_tester.data import KERNEL_MODULE_CONTAINER
from bci_tester.data import KIOSK_FIREFOX_CONTAINERS
from bci_tester.data import KIOSK_PULSEAUDIO_CONTAINERS
from bci_tester.data import KIOSK_XORG_CLIENT_CONTAINERS
from bci_tester.data import KIOSK_XORG_CONTAINERS
from bci_tester.data import KIWI_CONTAINERS
from bci_tester.data import KUBECTL_CONTAINERS
from bci_tester.data import KUBEVIRT_CDI_CONTAINERS
from bci_tester.data import KUBEVIRT_CONTAINERS
from bci_tester.data import L3_CONTAINERS
from bci_tester.data import LMCACHE_LMSTACK_ROUTER_CONTAINER
from bci_tester.data import LMCACHE_VLLM_OPENAI_CONTAINER
from bci_tester.data import LTSS_BASE_CONTAINERS
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import MARIADB_CLIENT_CONTAINERS
from bci_tester.data import MARIADB_CONTAINERS
from bci_tester.data import MICRO_CONTAINER
from bci_tester.data import MICRO_FIPS_CONTAINER
from bci_tester.data import MILVUS_CONTAINER
from bci_tester.data import MINIMAL_CONTAINER
from bci_tester.data import NGINX_CONTAINER
from bci_tester.data import NODEJS_CONTAINERS
from bci_tester.data import OLLAMA_CONTAINER
from bci_tester.data import OPENJDK_CONTAINERS
from bci_tester.data import OPENJDK_DEVEL_CONTAINERS
from bci_tester.data import OPENWEBUI_CONTAINER
from bci_tester.data import OPENWEBUI_PIPELINES_CONTAINER
from bci_tester.data import OPEN_WEBUI_MCPO_CONTAINER
from bci_tester.data import OS_SP_VERSION
from bci_tester.data import OS_VERSION
from bci_tester.data import OS_VERSION_ID
from bci_tester.data import PCP_CONTAINERS
from bci_tester.data import PC_AWS_TOOLCHAIN_RUNTIME_PROVIDER_CONTAINER
from bci_tester.data import PC_AZ_TOOLCHAIN_RUNTIME_PROVIDER_CONTAINER
from bci_tester.data import PC_GCP_TOOLCHAIN_RUNTIME_PROVIDER_CONTAINER
from bci_tester.data import PHP_8_APACHE
from bci_tester.data import PHP_8_CLI
from bci_tester.data import PHP_8_FPM
from bci_tester.data import POSTFIX_CONTAINERS
from bci_tester.data import POSTGRESQL_CONTAINERS
from bci_tester.data import PROMETHEUS_CONTAINERS
from bci_tester.data import PYTHON_CONTAINERS
from bci_tester.data import PYTORCH_CONTAINER
from bci_tester.data import RELEASED_LTSS_VERSIONS
from bci_tester.data import RMT_CONTAINERS
from bci_tester.data import RUBY_CONTAINERS
from bci_tester.data import RUST_CONTAINERS
from bci_tester.data import SAMBA_CLIENT_CONTAINERS
from bci_tester.data import SAMBA_SERVER_CONTAINERS
from bci_tester.data import SAMBA_TOOLBOX_CONTAINERS
from bci_tester.data import SPACK_CONTAINERS
from bci_tester.data import SPR_CONTAINERS
from bci_tester.data import STUNNEL_CONTAINER
from bci_tester.data import SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME
from bci_tester.data import SUSE_AI_OBSERVABILITY_EXTENSION_SETUP
from bci_tester.data import TARGET
from bci_tester.data import TOMCAT_CONTAINERS
from bci_tester.data import VALKEY_CONTAINERS
from bci_tester.data import VLLM_OPENAI_CONTAINER
from bci_tester.data import ImageType
from bci_tester.runtime_choice import PODMAN_SELECTED

#: The official vendor name
VENDOR = "openSUSE Project" if OS_VERSION == "tumbleweed" else "SUSE LLC"

SKIP_IF_TW_MARK = pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="no supportlevel labels on openSUSE containers",
)

SKIP_IF_AI_MARK = pytest.mark.skipif(
    OS_VERSION == "15.6-ai", reason="no supportlevel labels on AI containers"
)
SKIP_IF_LTSS_VERSION = pytest.mark.skipif(
    OS_VERSION in RELEASED_LTSS_VERSIONS, reason="LTSS container"
)
SKIP_IF_PC_MARK = pytest.mark.skipif(
    OS_VERSION == "16.0-pc2025",
    reason="not for Public Cloud Toolchain containers",
)


def _get_container_label_prefix(
    container_name: str, container_type: ImageType
) -> str:
    if OS_VERSION == "16.0-pc2025" and container_type == ImageType.APPLICATION:
        return f"com.suse.public-cloud-toolchain.{container_name}"

    if OS_VERSION == "tumbleweed" and container_name == "base":
        return "org.opensuse.base"
    if OS_VERSION == "tumbleweed":
        return f"org.opensuse.{container_type}.{container_name}"
    if container_type == ImageType.OS_LTSS:
        return f"com.suse.sle.{container_name}"

    return f"com.suse.{container_type}.{container_name}"


def _get_container_ref(
    container_reference: str, container_type: ImageType
) -> str:
    name, version_release = container_reference.split(":")
    if container_type == ImageType.OS:
        return (
            f"{name}:latest"
            if OS_VERSION == "tumbleweed"
            else f"{name}:{OS_VERSION}"
        )

    non_release_ref = (
        version_release.rpartition("-")[0]
        if "-" in version_release
        else version_release
    )
    return f"{name}:{non_release_ref}"


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
        (MICRO_FIPS_CONTAINER, "micro-fips", ImageType.OS),
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
        (INIT_CONTAINER, "init", ImageType.OS),
        (PHP_8_APACHE, "php-apache", ImageType.LANGUAGE_STACK),
        (PHP_8_CLI, "php", ImageType.LANGUAGE_STACK),
        (PHP_8_FPM, "php-fpm", ImageType.LANGUAGE_STACK),
        (NGINX_CONTAINER, "nginx", ImageType.APPLICATION),
    ]
    + [(c, "openjdk", ImageType.LANGUAGE_STACK) for c in OPENJDK_CONTAINERS]
    + [
        (c, "openjdk.devel", ImageType.LANGUAGE_STACK)
        for c in OPENJDK_DEVEL_CONTAINERS
    ]
    + [
        (c, "firefox-esr", ImageType.APPLICATION)
        for c in KIOSK_FIREFOX_CONTAINERS
    ]
    + [
        (c, "pulseaudio", ImageType.APPLICATION)
        for c in KIOSK_PULSEAUDIO_CONTAINERS
    ]
    + [(c, "xorg", ImageType.APPLICATION) for c in KIOSK_XORG_CONTAINERS]
    + [
        (c, "xorg-client", ImageType.APPLICATION)
        for c in KIOSK_XORG_CLIENT_CONTAINERS
    ]
    + [(c, "nodejs", ImageType.LANGUAGE_STACK) for c in NODEJS_CONTAINERS]
    + [(c, "python", ImageType.LANGUAGE_STACK) for c in PYTHON_CONTAINERS]
    + [(c, "ruby", ImageType.LANGUAGE_STACK) for c in RUBY_CONTAINERS]
    + [(c, "base-fips", ImageType.OS) for c in BASE_FIPS_CONTAINERS]
    + [
        (container_pcp, "pcp", ImageType.APPLICATION)
        for container_pcp in PCP_CONTAINERS
    ]
    + [(kiwi, "kiwi", ImageType.LANGUAGE_STACK) for kiwi in KIWI_CONTAINERS]
    + [
        (tomcat_ctr, "apache-tomcat", ImageType.APPLICATION)
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
        (postfix_container, "postfix", ImageType.APPLICATION)
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
                DOTNET_SDK_10_0_CONTAINER,
                "dotnet.sdk",
                ImageType.LANGUAGE_STACK,
            ),
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
                DOTNET_ASPNET_10_0_CONTAINER,
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
            (
                DOTNET_RUNTIME_10_0_CONTAINER,
                "dotnet.runtime",
                ImageType.LANGUAGE_STACK,
            ),
        ]
        if LOCALHOST.system_info.arch in ("aarch64", "x86_64")
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
        (
            SUSE_AI_OBSERVABILITY_EXTENSION_SETUP,
            "suse-ai-observability-extension-setup",
            ImageType.SAC_APPLICATION,
        ),
        (
            SUSE_AI_OBSERVABILITY_EXTENSION_RUNTIME,
            "suse-ai-observability-extension-runtime",
            ImageType.SAC_APPLICATION,
        ),
        (
            OPENWEBUI_PIPELINES_CONTAINER,
            "open-webui-pipelines",
            ImageType.SAC_APPLICATION,
        ),
        (VLLM_OPENAI_CONTAINER, "vllm-openai", ImageType.SAC_APPLICATION),
        (
            LMCACHE_VLLM_OPENAI_CONTAINER,
            "lmcache-vllm-openai",
            ImageType.SAC_APPLICATION,
        ),
        (
            LMCACHE_LMSTACK_ROUTER_CONTAINER,
            "lmcache-lmstack-router",
            ImageType.SAC_APPLICATION,
        ),
        (
            OPEN_WEBUI_MCPO_CONTAINER,
            "open-webui-mcpo",
            ImageType.SAC_APPLICATION,
        ),
        (
            PC_AWS_TOOLCHAIN_RUNTIME_PROVIDER_CONTAINER,
            "aws-toolchain-runtime-provider",
            ImageType.APPLICATION,
        ),
        (
            PC_AZ_TOOLCHAIN_RUNTIME_PROVIDER_CONTAINER,
            "az-toolchain-runtime-provider",
            ImageType.APPLICATION,
        ),
        (
            PC_GCP_TOOLCHAIN_RUNTIME_PROVIDER_CONTAINER,
            "google-toolchain-runtime-provider",
            ImageType.APPLICATION,
        ),
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
    + [
        (valkey_container, "valkey", ImageType.APPLICATION)
        for valkey_container in VALKEY_CONTAINERS
    ]
    + [
        (bind_ctr, "bind", ImageType.APPLICATION)
        for bind_ctr in BIND_CONTAINERS
    ]
    + [
        (samba_ctr, "samba-server", ImageType.APPLICATION)
        for samba_ctr in SAMBA_SERVER_CONTAINERS
    ]
    + [
        (samba_ctr, "samba-client", ImageType.APPLICATION)
        for samba_ctr in SAMBA_CLIENT_CONTAINERS
    ]
    + [
        (samba_ctr, "samba-toolbox", ImageType.APPLICATION)
        for samba_ctr in SAMBA_TOOLBOX_CONTAINERS
    ]
    + [(rmt, "rmt-server", ImageType.APPLICATION) for rmt in RMT_CONTAINERS]
    + [
        (
            app_ctr,
            container_and_marks_from_pytest_param(app_ctr)[0]
            .baseurl.rpartition("/")[2]
            .rpartition(":")[0],
            ImageType.APPLICATION,
        )
        for app_ctr in SPR_CONTAINERS
        + KUBEVIRT_CONTAINERS
        + KUBEVIRT_CDI_CONTAINERS
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
            elif OS_VERSION in ("15.6-spr",):
                assert (
                    "for SUSE Private Registry"
                    in labels[f"{prefix}.description"]
                )
            elif OS_VERSION in ("16.0-pc2025",):
                assert (
                    "Use this container when building a transparent"
                    in labels[f"{prefix}.description"]
                )
            else:
                assert (
                    "based on the SLE Base Container Image."
                    in labels[f"{prefix}.description"]
                    or "based on the SUSE Linux Enterprise Base Container Image."
                    in labels[f"{prefix}.description"]
                    or "based on the SUSE Linux Base Container Image."
                    in labels[f"{prefix}.description"]
                )

        if version == "tumbleweed":
            assert OS_VERSION in labels[f"{prefix}.version"]

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
                "https://www.suse.com/lifecycle#suse-linux-enterprise-server-16",
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
def test_url(
    container: ContainerData,
    container_name: str,
    container_type: ImageType,
):
    """
    Check if label ``com.suse.bci.$name.url`` equals :py:const:`URL`
    """

    labels = container.inspect.config.labels

    for prefix in (
        _get_container_label_prefix(container_name, container_type),
        "org.opencontainers.image",
    ):
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
        elif OS_VERSION == "16.0-pc2025":
            expected_url = ("https://www.suse.com",)
        elif container_type in (
            ImageType.SAC_LANGUAGE_STACK,
            ImageType.SAC_APPLICATION,
        ):
            container_mapping: dict[str, str] = {
                "lmcache-lmstack-router": "vllm",
                "lmcache-vllm-openai": "vllm",
            }
            expected_url = (
                f"https://apps.rancher.io/applications/{container_mapping.get(container_name, container_name)}",
                f"https://apps.rancher.io/applications/{container_name.rpartition('-')[0]}",
            )
        elif container_type == ImageType.OS_LTSS:
            expected_url = (
                "https://www.suse.com/products/long-term-service-pack-support/",
            )

        assert labels[f"{prefix}.url"] in expected_url, (
            f"expected LABEL {prefix}.url = {expected_url} but is {labels[f'{prefix}.url']}"
        )


@SKIP_IF_PC_MARK
@SKIP_IF_AI_MARK
@SKIP_IF_LTSS_VERSION
@pytest.mark.parametrize(
    "container",
    [cont for cont in ALL_CONTAINERS if cont != BASE_CONTAINER],
    indirect=True,
)
def test_artifacthub_urls(container: ContainerData) -> None:
    """Smoke test checking that the artifacthub.io labelling is passing sanity checks"""
    labels = container.inspect.config.labels

    assert "io.artifacthub.package.readme-url" in labels, (
        "readme url missing in labels"
    )
    readme_url = urllib.parse.urlparse(
        labels["io.artifacthub.package.readme-url"]
    )

    assert readme_url.scheme == "https"
    assert readme_url.netloc in (
        "github.com",
        "build.opensuse.org",
        "sources.suse.com",
    ), f"readme-url points to unexpected host {readme_url.netloc}"
    assert readme_url.port is None

    # for devel projects we pass it as a query
    assert readme_url.path.endswith(".md")
    assert "/README" in readme_url.path
    assert "//" not in readme_url.path and "//" not in readme_url.path
    # TODO(dmllr): add testing for logo-url


@pytest.mark.parametrize(
    "container,container_name,container_type",
    IMAGES_AND_NAMES,
    indirect=["container"],
)
def test_support_end_in_future(
    container: ContainerData,
    container_name: str,
    container_type: ImageType,  # pylint: disable=unused-argument
):
    labels = container.inspect.config.labels
    if "com.suse.supportlevel.until" in labels:
        if container_type in (
            ImageType.SAC_APPLICATION,
            ImageType.SAC_LANGUAGE_STACK,
        ):
            pytest.skip(
                reason="SAC containers do not properly define a supportlevel"
            )
        try:
            # python 3.7+
            support_end: datetime.datetime = datetime.datetime.fromisoformat(
                labels["com.suse.supportlevel.until"]
            )
        except AttributeError:
            support_end = datetime.datetime.strptime(
                labels["com.suse.supportlevel.until"], "%Y-%m-%d"
            )
        assert datetime.datetime.now() < support_end, (
            f"container out of {support_end}"
        )


@pytest.mark.skipif(
    OS_VERSION == "15.6-spr",
    reason="SPR publishes out of the devel project",
)
@pytest.mark.skipif(
    TARGET == "custom",
    reason="disturl can be anything if TARGET=custom",
)
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
    baseurl = urllib.parse.urlparse(
        f"oci://{container.container.get_base().url}"
    )
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
    elif OS_VERSION == "15.6-ai" and TARGET in ("ibs", "obs"):
        assert "obs://build.suse.de/Devel:AI" in disturl
    elif OS_VERSION == "15.6-spr" and TARGET in ("ibs", "obs"):
        assert "obs://build.suse.de/Devel:SCC:PrivateRegistry" in disturl
    elif OS_VERSION == "16.0-pc2025":
        assert (
            "obs://build.suse.de/SUSE:SLFO:Products:PublicCloud:Toolchain:2025"
            in disturl
        )
    elif OS_VERSION == "16.0":
        if baseurl.netloc == "registry.opensuse.org":
            assert (
                f"obs://build.opensuse.org/devel:BCI:16.{OS_SP_VERSION}"
                in disturl
            )
        else:
            assert (
                f"obs://build.suse.de/SUSE:SLFO:Products:BCI:16.{OS_SP_VERSION}"
                in disturl
            )
    else:
        if baseurl.netloc == "registry.opensuse.org":
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
@SKIP_IF_AI_MARK
@pytest.mark.parametrize(
    "container",
    [
        cont
        for cont in ALL_CONTAINERS
        if (cont not in L3_CONTAINERS and cont not in ACC_CONTAINERS)
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
@SKIP_IF_AI_MARK
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
@SKIP_IF_AI_MARK
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
    elif OS_VERSION in ("15.6-spr",):
        assert reference.startswith("registry.suse.com/private-registry/")
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
    ref = _get_container_ref(reference, container_type)

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


def _reg(registry: str, repository: str, otype: str, object: str) -> Any:
    r = requests.get(
        f"https://{registry}/v2/{repository}/{otype}/{object}",
        timeout=5,
        allow_redirects=False,
        verify=not registry.endswith("suse.de"),
        headers={"User-Agent": "github.com/SUSE/BCI-tests"},
    )
    return r.json()


@pytest.mark.skipif(
    OS_VERSION not in ("15.7",), reason="Does not have buildtime attestations"
)
@pytest.mark.parametrize(
    "container",
    [
        MICRO_CONTAINER,
        MICRO_FIPS_CONTAINER,
        BASE_CONTAINER,
        *BASE_FIPS_CONTAINERS,
        BUSYBOX_CONTAINER,
    ],
    indirect=["container"],
)
def test_buildtime_attestations(container):
    baseurl = urllib.parse.urlparse(
        f"oci://{container.container.get_base().url}"
    )
    repository, _, tag = baseurl.path.partition(":")

    container_reference = container.inspect.config.labels[
        "org.opensuse.reference"
    ]
    assert container_reference

    digest = None
    # Find the match for the local architecture in the fat manifest
    fat_manifest = _reg(baseurl.netloc, repository, "manifests", tag)
    assert fat_manifest["schemaVersion"] == 2
    for manifest in fat_manifest["manifests"]:
        local_arch = {"aarch64": "arm64", "x86_64": "amd64"}.get(
            LOCALHOST.system_info.arch, LOCALHOST.system_info.arch
        )
        if manifest["platform"]["architecture"] == local_arch:
            digest = manifest["digest"]
            break

    assert digest, (
        f"No manifest found for architecture {LOCALHOST.system_info.arch}"
    )
    # Fetch the attestation for the specific architecture
    attestation = _reg(
        baseurl.netloc,
        repository,
        "manifests",
        digest.replace("sha256:", "sha256-") + ".att",
    )
    got_clamav: bool = False
    # Trivy is not scanning on s390x architecture
    got_trivy: bool = manifest["platform"]["architecture"] in ("s390x",)
    # NeuVector is only scanning on x86_64 and aarch64, so skip on ppc64le and s390x
    got_neuvector: bool = manifest["platform"]["architecture"] in (
        "ppc64le",
        "s390x",
    )
    for layer in attestation["layers"]:
        predicate_type = layer.get("annotations", {}).get(
            "org.open-build-service.intoto.predicatetype", None
        )
        predicate = _reg(baseurl.netloc, repository, "blobs", layer["digest"])

        payload = json.loads(base64.b64decode(predicate["payload"]))
        assert digest.endswith(payload["subject"][0]["digest"]["sha256"])

        if predicate_type == "https://cosign.sigstore.dev/attestation/v1":
            assert not got_clamav
            got_clamav = True
            clamav_result = payload["predicate"]["data"]
            assert "Infected files: 0" in clamav_result

            virus_count_found = False
            files_count_found = False
            for r in clamav_result.splitlines():
                if r.startswith("Known viruses: "):
                    assert int(r.partition(":")[2]) > 100000, (
                        f"{clamav_result} does not have at least 100000 signatures"
                    )
                    virus_count_found = True
                if r.startswith("Scanned files: "):
                    assert int(r.partition(":")[2]) >= 200, (
                        f"{clamav_result} does not have at least 200 files scanned"
                    )
                    files_count_found = True

            assert virus_count_found and files_count_found
            assert 500 < len(predicate["payload"]) < 1000, (
                "ClamAV scan result has unusual length"
            )
            continue
        if not predicate_type.endswith("/vuln/v1"):
            assert 10000 < len(predicate["payload"]) < 10000000, (
                f"Attestation payload length {len(predicate['payload'])} outside range"
            )
            continue

        scanner = payload["predicate"]["scanner"]
        result = scanner["result"]
        if "aquasecurity/trivy" in scanner["uri"]:
            assert not got_trivy, (
                f"Multiple Trivy attestations for {manifest['platform']['architecture']}"
            )
            got_trivy = True

            trivy_reference = result["Metadata"]["ImageConfig"]["config"][
                "Labels"
            ]["org.opensuse.reference"]
            assert container_reference == trivy_reference, (
                f"Unexpected reference {trivy_reference} in trivy report"
            )

            for finding in result["Results"]:
                assert "Vulnerabilities" not in finding, (
                    f"Image has vulnerability {finding['Vulnerabilities'][0]['VulnerabilityID']}"
                )
            assert "Class" in result["Results"][0]
        elif "neuvector/scanner" in scanner["uri"]:
            assert not got_neuvector, (
                f"Multiple NeuVector attestations for {manifest['platform']['architecture']}"
            )
            got_neuvector = True
            assert scanner["db"]["uri"]
            if "error_message" in result:
                assert len(result["error_message"]) == 0
            for check in result["report"]["checks"]:
                assert check["level"] in ("WARN",), (
                    f"Neuvector file {check['description']}"
                )

            # for some reason, NeuVector cannot extract labels from kiwi type containers
            if "labels" in result["report"]:
                assert (
                    container_reference
                    == result["report"]["labels"]["org.opensuse.reference"]
                )
        assert 10000 < len(predicate["payload"]) < 1000000, (
            f"Vulnerability report length {len(predicate['payload'])} outside range"
        )
    assert got_clamav, (
        f"ClamAV missing for {manifest['platform']['architecture']}"
    )
    assert got_neuvector, (
        f"NeuVector missing for {manifest['platform']['architecture']}"
    )
    assert got_trivy, (
        f"Trivy missing for {manifest['platform']['architecture']}"
    )
