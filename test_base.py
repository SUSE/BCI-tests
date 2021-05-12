from matryoshka_tester.fips import NONFIPS_DIGESTS, FIPS_DIGESTS, ALL_DIGESTS
from conftest import with_fips, without_fips


def test_passwd_present(container):
    assert container.file("/etc/passwd").exists


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
