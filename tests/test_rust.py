"""Tests for the Rust development container.

Rust development containers include rust and cargo.
"""

import pytest
from pytest_container import GitRepositoryBuild

from bci_tester.data import RUST_CONTAINERS
from bci_tester.fips import host_fips_enabled

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


# On a FIPS enabled host, most of these tests fail with one of these:
#   "unsupported"
#   "initialization error"
#   "invalid padding mode"
#   "key gen error"
#   "mac verify failure"
# Be aware that the skip rule matches partially, thus, a few more tests are
# skipped, but that is acceptable.
RUST_OPENSSL_FIPS_SKIP = (
    [
        "cipher_ctx::test::full_block_updates_3des",
        "cipher_ctx::test::seal_open",
        "cms::test::cms_encrypt_decrypt",
        "cms::test::cms_sign_verify_error",
        "derive::test::derive_undersized_buffer",
        "dsa::test::test_signature",
        "ec::test::test_password_callback_oversize_return_is_rejected",
        "encrypt::test::rsa_encrypt_decrypt",
        "envelope::test::public_encrypt_private_decrypt",
        "hash::tests::test_clone",
        "hash::tests::test_finish_twice",
        "hash::tests::test_md5",
        "hash::tests::test_sm3",
        "kdf::tests::argon2",
        "pkcs12::test::create",
        "pkcs12::test::parse",
        "pkcs5::tests::scrypt",
        "pkcs7::tests::encrypt_decrypt_test",
        "pkey::tests::test_encrypted_pkcs8",
        "pkey::tests::test_raw_private_key_bytes",
        "pkey::tests::test_raw_public_key_bytes",
        "pkey_ctx::test::derive_undersized_buffer",
        "pkey_ctx::test::dh_paramgen",
        "pkey_ctx::test::dsa_paramgen",
        "pkey_ctx::test::ecdsa_deterministic_signature",
        "pkey_ctx::test::rsa",
        "rsa::test::test_check_key",
        "rsa::test::test_from_password",
        "rsa::test::test_to_password",
        "sign::test::hmac_md5",
        "ssl::test::peer_tmp_key_rsa",
        "ssl::test::tmp_dh_callback",
        "symm::tests::test_aes_128_ocb",
        "symm::tests::test_chacha20",
        "symm::tests::test_des",
        "symm::tests::test_rc4",
        "symm::tests::test_sm4",
    ]
    if host_fips_enabled()
    else []
)

RUST_OPENSSL_FIPS_SKIP_LIST = " ".join(
    f"--skip {test}" for test in RUST_OPENSSL_FIPS_SKIP
)


@pytest.mark.parametrize(
    "container_git_clone",
    [
        pkg.to_pytest_param()
        for pkg in (
            GitRepositoryBuild(
                repository_url="https://github.com/sfackler/rust-openssl",
                build_command=f"zypper -n in libopenssl-devel && cargo build && cargo test --lib -- {RUST_OPENSSL_FIPS_SKIP_LIST}",
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
