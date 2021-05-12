import os


NONFIPS_DIGESTS = (
    "blake2b512",
    "blake2s256",
    "gost",
    "md4",
    "md5",
    "mdc2",
    "rmd160",
    "sm3",
)

FIPS_DIGESTS = (
    "sha1",
    "sha224",
    "sha256",
    "sha3-224",
    "sha3-256",
    "sha3-384",
    "sha3-512",
    "sha384",
    "sha512",
    "sha512-224",
    "sha512-256",
    "shake128",
    "shake256",
)

ALL_DIGESTS = NONFIPS_DIGESTS + FIPS_DIGESTS


def host_fips_supported():
    return os.path.exists("/proc/sys/crypto/fips_enabled")


def host_fips_enabled():
    if not host_fips_supported():
        return False

    with open("/proc/sys/crypto/fips_enabled") as f:
        return f.read().strip() == "1"
