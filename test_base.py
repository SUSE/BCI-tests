import pytest
from bci_tester.fips import (
    host_fips_enabled,
    NONFIPS_DIGESTS,
    FIPS_DIGESTS,
    ALL_DIGESTS,
)

#: 100MB limit for the base container
BASE_CONTAINER_MAX_SIZE = 120 * 1024 * 1024


# Generic tests
def test_passwd_present(auto_container):
    assert auto_container.connection.file("/etc/passwd").exists


def test_base_size(auto_container, container_runtime):
    assert (
        container_runtime.get_image_size(auto_container.image_url)
        < BASE_CONTAINER_MAX_SIZE
    )


# FIPS tests
with_fips = pytest.mark.skipif(
    not host_fips_enabled(), reason="host not running in FIPS 140 mode"
)
without_fips = pytest.mark.skipif(
    host_fips_enabled(), reason="host running in FIPS 140 mode"
)


@with_fips
def test_openssl_fips_hashes(auto_container):
    for md in NONFIPS_DIGESTS:
        cmd = auto_container.connection.run(f"openssl {md} /dev/null")
        assert cmd.rc != 0
        assert "not a known digest" in cmd.stderr

    for md in FIPS_DIGESTS:
        auto_container.connection.run_expect([0], f"openssl {md} /dev/null")


@without_fips
def test_openssl_hashes(auto_container):
    for md in ALL_DIGESTS:
        auto_container.connection.run_expect([0], f"openssl {md} /dev/null")
