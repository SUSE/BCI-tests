import pytest
from matryoshka_tester.fips import (
    host_fips_enabled,
    NONFIPS_DIGESTS,
    FIPS_DIGESTS,
    ALL_DIGESTS,
)

#: 100MB limit for the base container
BASE_CONTAINER_MAX_SIZE = 100 * 1024 * 1024


# Generic tests
def test_passwd_present(container):
    assert container.connection.file("/etc/passwd").exists


def test_base_size(container, container_runtime):
    assert (
        container_runtime.get_image_size(container.image)
        < BASE_CONTAINER_MAX_SIZE
    )


def test_grep_absent(container):
    assert not container.connection.exists("grep")


# FIPS tests
with_fips = pytest.mark.skipif(
    not host_fips_enabled(), reason="host not running in FIPS 140 mode"
)
without_fips = pytest.mark.skipif(
    host_fips_enabled(), reason="host running in FIPS 140 mode"
)


@with_fips
def test_openssl_fips_hashes(container):
    for md in NONFIPS_DIGESTS:
        cmd = container.connection.run(f"openssl {md} /dev/null")
        assert cmd.rc != 0
        assert "not a known digest" in cmd.stderr

    for md in FIPS_DIGESTS:
        container.connection.run_expect([0], f"openssl {md} /dev/null")


@without_fips
def test_openssl_hashes(container):
    for md in ALL_DIGESTS:
        container.connection.run_expect([0], f"openssl {md} /dev/null")
