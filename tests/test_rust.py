"""Tests for the Rust development container.

Rust development containers include rust and cargo.
"""

import pytest
from pytest_container import GitRepositoryBuild

from bci_tester.data import OS_VERSION
from bci_tester.data import RUST_CONTAINERS

CONTAINER_IMAGES = RUST_CONTAINERS


def test_rust_version(auto_container):
    """Check that the environment variable ``RUST_VERSION`` matches the actual
    version of :command:`rustc`.

    """
    assert (
        auto_container.connection.check_output("echo $RUST_VERSION")
        == auto_container.connection.check_output("rustc --version").split()[1]
    )


def test_cargo_version(auto_container):
    """Check that the environment variable ``CARGO_VERSION`` matches the actual
    version of :command:`cargo`.

    """
    assert (
        auto_container.connection.check_output("echo $CARGO_VERSION")
        == auto_container.connection.check_output("cargo --version").split()[1]
    )


@pytest.mark.parametrize(
    "container_git_clone",
    [
        pkg.to_pytest_param()
        for pkg in (
            GitRepositoryBuild(
                repository_url="https://github.com/sfackler/rust-openssl",
                build_command="zypper -n in libopenssl-devel && cargo build && cargo test",
                marks=(
                    None
                    if OS_VERSION != "tumbleweed"
                    else pytest.mark.xfail(
                        reason=(
                            "broken test on Tumbleweed due to disabled prime curves,"
                            "see https://github.com/sfackler/rust-openssl/pull/2330"
                        )
                    )
                ),
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/rust-random/rand",
                build_command="cargo build && cargo test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/dtolnay/syn",
                build_command="cargo build && cargo check --all-features",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/dtolnay/quote",
                build_command="cargo test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/alexcrichton/cfg-if",
                build_command="cargo test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/dtolnay/proc-macro2",
                build_command=(
                    "cargo test && cargo test --no-default-features && "
                    "cargo test --features span-locations && "
                    "RUSTFLAGS='--cfg procmacro2_semver_exempt' cargo test && "
                    "RUSTFLAGS='--cfg procmacro2_semver_exempt' cargo test --no-default-features"
                ),
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/unicode-rs/unicode-xid",
                build_command="cargo build && cargo test",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/serde-rs/serde",
                build_command="pushd serde && cargo build --features rc && cargo build --no-default-features && popd && pushd test_suite && cargo build && cargo test --features serde/derive,serde/rc",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/bitflags/bitflags",
                build_command="cargo test --features example_generated",
            ),
        )
    ],
    indirect=["container_git_clone"],
)
def test_crate_builds(auto_container_per_test, container_git_clone):
    """Try to build & test the most downloaded crates from
    `<https://crates.io/>`_.

    """
    auto_container_per_test.connection.run_expect(
        [0], container_git_clone.test_command
    )
