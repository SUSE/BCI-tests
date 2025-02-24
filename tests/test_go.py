"""Tests for the Go language container."""

import re
from pathlib import Path
from typing import Tuple

import pytest
from packaging import version
from pytest_container import GitRepositoryBuild
from pytest_container.container import ContainerData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import BASE_CONTAINER
from bci_tester.data import GOLANG_CONTAINERS
from bci_tester.runtime_choice import DOCKER_SELECTED

#: Maximum go container size in Bytes
GOLANG_MAX_CONTAINER_SIZE_ON_DISK = 1181116006  # 1.1GB uncompressed

CONTAINER_IMAGES = GOLANG_CONTAINERS


def test_go_size(auto_container, container_runtime):
    """Ensure that the go base container is below the size specified in
    :py:const:`GOLANG_MAX_CONTAINER_SIZE_ON_DISK`.

    """
    assert (
        container_runtime.get_image_size(auto_container.image_url_or_id)
        < GOLANG_MAX_CONTAINER_SIZE_ON_DISK
    )


def test_go_version(auto_container):
    """Check that the environment variable ``GOLANG_VERSION`` matches the output of
    :command:`go version`

    """
    assert auto_container.connection.check_output(
        "echo $GOLANG_VERSION"
    ) in auto_container.connection.check_output("go version")


@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/weaveworks/kured.git",
            repository_tag="1.13.2",
            build_command="env GOMAXPROCS=2 go run ./cmd/kured -h && go test -race ./...",
        ).to_pytest_param(),
    ],
    indirect=["container_git_clone"],
)
def test_build_kured(auto_container_per_test, container_git_clone):
    """Try to build `kured <https://github.com/weaveworks/kured.git>`_ inside the
    container with :command:`make` pre-installed.

    The documented way to build kured is `make bootstrap-tools kured` however
    that requires goreleaser which isn't available on all the architectures that
    we care about. So we hardcode a specific version and build it directly.

    """
    auto_container_per_test.connection.check_output(
        container_git_clone.test_command
    )


@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/helm/helm.git",
            repository_tag="v3.16.4",
            build_command="env GOMAXPROCS=2 make build test-unit",
        ).to_pytest_param(),
    ],
    indirect=["container_git_clone"],
)
def test_build_helm(auto_container_per_test, container_git_clone):
    """Try to build `helm <https://github.com/helm/helm.git>`_ inside the
    container with :command:`make` pre-installed.

    """

    auto_container_per_test.connection.check_output(
        container_git_clone.test_command
    )


def test_go_get_binary_in_path(auto_container_per_test):
    """Check that binaries installed via ``go install`` can be invoked (i.e. are in
    the ``$PATH``).

    """
    auto_container_per_test.connection.check_output(
        "go install github.com/tylertreat/comcast@latest"
    )
    assert "Comcast" in auto_container_per_test.connection.check_output(
        "comcast -version"
    )


@pytest.mark.parametrize("container", [BASE_CONTAINER], indirect=True)
def test_base_PATH_present(auto_container, container):
    """Regression test that we did not accidentally omit parts of ``$PATH`` that are
    present in he base container in the golang containers.

    """
    path_in_go_container = auto_container.connection.check_output("echo $PATH")
    path_in_base_container = container.connection.check_output("echo $PATH")
    assert path_in_base_container in path_in_go_container


@pytest.mark.parametrize(
    "container_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/Code-Hex/go-generics-cache.git",
            repository_tag="v1.0.1",
            build_command="go test ./...",
        )
    ],
    indirect=True,
)
def test_build_generics_cache(
    auto_container_per_test: ContainerData, container_git_clone
):
    """Test generics by running the tests of `go-generics-cache
    <https://github.com/Code-Hex/go-generics-cache>`_ inside the
    container.
    """
    auto_container_per_test.connection.check_output(
        container_git_clone.test_command
    )


@pytest.mark.parametrize(
    "container",
    GOLANG_CONTAINERS,
    indirect=["container"],
)
@pytest.mark.parametrize(
    "host_git_clone",
    [
        GitRepositoryBuild(
            repository_url="https://github.com/rancher/rancher",
        ).to_pytest_param()
    ],
    indirect=["host_git_clone"],
)
@pytest.mark.skipif(
    not DOCKER_SELECTED, reason="Dapper only works with docker"
)
@pytest.mark.skipif(
    LOCALHOST.system_info.arch not in ("x86_64", "aarch64"),
    reason=f"{LOCALHOST.system_info.arch} is not supported to build rancher",
)
def test_rancher_build(
    host,
    host_git_clone: Tuple[Path, GitRepositoryBuild],
    dapper,
    container: ContainerData,
):
    """Regression test that we can build Rancher in the go container:

    - clone the `rancher/rancher <https://github.com/rancher/rancher>`_ repository
    - monkey patch their :file:`Dockerfile.dapper` replacing their container
      image with the url or id of the go container
    - check that the go version from go.mod is smaller than the current go
      compiler version, and if it isn't, skip this test
    - run :command:`dapper build`

    This test is only enabled for docker (dapper does not support podman).
    """
    dest, git_repo = host_git_clone
    rancher_dir = dest / git_repo.repo_name
    with open(
        rancher_dir / "Dockerfile.dapper", encoding="utf-8"
    ) as dapperfile:
        contents = dapperfile.read(-1)

    from_line_regex = re.compile(
        r"^from registry\.suse\.com/bci/golang:(?P<go_ver>.*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    from_line = from_line_regex.match(contents)

    assert from_line and from_line.group("go_ver"), (
        f"No valid FROM line found in Dockerfile.dapper: {contents}"
    )

    go_version = container.inspect.config.env["GOLANG_VERSION"]
    go_version_match = re.search(
        r"^go\s+(?P<version>(\d+\.?)+)$",
        (rancher_dir / "go.mod").read_text(),
        re.MULTILINE,
    )
    assert go_version_match and go_version_match.group("version")

    go_mod_version = version.parse(go_version_match.group("version"))
    if go_mod_version > version.parse(go_version):
        pytest.skip(f"Rancher requires {go_mod_version}, but got {go_version}")

    (rancher_dir / "Dockerfile.dapper").write_text(
        from_line_regex.sub(f"FROM {container.image_url_or_id}", contents)
    )

    host.check_output(f"cd {rancher_dir} && {dapper} build")
