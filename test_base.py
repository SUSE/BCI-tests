import pytest
from matryoshka_tester.fips import (
    host_fips_enabled,
    host_fips_supported,
    NONFIPS_DIGESTS,
    FIPS_DIGESTS,
    ALL_DIGESTS,
)


def test_passwd_present(container):
    assert container.connection.file("/etc/passwd").exists


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
        assert "not a known digest" in cmd.stdout

    for md in FIPS_DIGESTS:
        container.connection.run_expect([0], f"openssl {md} /dev/null")


@without_fips
def test_openssl_hashes(container):
    for md in ALL_DIGESTS:
        container.connection.run_expect([0], f"openssl {md} /dev/null")
