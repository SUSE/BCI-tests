"""Module containing utility functions & constants for FIPS compliant digests."""

import os
from typing import Dict
from typing import Tuple

from bci_tester.data import OS_VERSION

#: openssl digests that are not FIPS compliant
NONFIPS_DIGESTS: Tuple[str, ...] = (
    "blake2b512",
    "blake2s256",
    "md5",
    "rmd160",
    "sm3",
)

# OpenSSL 3.x in Tumbleweed dropped those as they're beyond deprecated
if OS_VERSION in ("15.3", "15.4", "15.5"):
    NONFIPS_DIGESTS += ("md4", "mdc2")

#: FIPS compliant openssl digests
FIPS_DIGESTS: Tuple[str, ...] = (
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

NULL_DIGESTS: Dict[str, str] = {
    "blake2b512": "786a02f742015903c6c6fd852552d272912f4740e15847618a86e217f71f5419d25e1031afee585313896444934eb04b903a685b1448b755d56f701afe9be2ce",
    "blake2s256": "69217a3079908094e11121d042354a7c1f55b6482ca1a51e1b250dfd1ed0eef9",
    "md5": "d41d8cd98f00b204e9800998ecf8427e",
    "rmd160": "9c1185a5c5e9fc54612808977ee8f548b2258d31",
    "sm3": "66c7f0f075ae7c3b8233c1a95f0d1f3b732d3cfe",
    "md4": "31d6cfe0d16ae931b73c59d7e0c089c0",
    "mdc2": "1e5f7c0f4a2a0d0a",
    "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
    "sha224": "d14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "sha3-224": "6b4e03423667dbb73b6e15454f0eb1abd4597f9a1b078e3f5b5a6bc7",
    "sha3-256": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a",
    "sha3-384": "0c63a75b845e4f7d01107d852e4c2485c51a50aaaa94fc61995e71bbee983a2ac3713831264adb47fb6bd1e058d5f004",
    "sha3-512": "a69f73cca23a9ac5c8b567dc185a756e97c982164fe25859e0d1dcc1475c80a615b2123af1f5f94c11e3e9402c3ac558f500199d95b6d3e301758586281dcd26",
    "sha384": "38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da274edebfe76f65fbd51ad2f14898b95b",
    "sha512": "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e",
    "sha512-224": "6ed0dd02806fa89e25de060c19d3ac86cabb87d6a0ddd05c333b84f4",
    "sha512-256": "c672b8d1ef56ed28ab87c3622c5114069bdd3ad7b8f9737498d0c01ecef0967a",
    "shake128": "7f9c2ba4e88f827d616045507605853e",
    "shake256": "46b9dd2b0ba88d13233b3feb743eeb243fcd52ea62b81b82b50c27646ed5762f",
}

#: all digests supported by openssl
ALL_DIGESTS: Tuple[str, ...] = NONFIPS_DIGESTS + FIPS_DIGESTS

assert len(set(ALL_DIGESTS)) == len(ALL_DIGESTS)

#: gnutls digests that are not FIPS compliant
NONFIPS_GNUTLS_DIGESTS: Tuple[str, ...] = (
    "md5",
    "gostr341194",
    "streebog-256",
    "streebog-512",
)

#: FIPS compliant gnutls digests
FIPS_GNUTLS_DIGESTS: Tuple[str, ...] = (
    "sha1",
    "sha224",
    "sha256",
    "sha384",
    "sha512",
)

#: all digests supported by gnutls
ALL_GNUTLS_DIGESTS: Tuple[str, ...] = (
    NONFIPS_GNUTLS_DIGESTS + FIPS_GNUTLS_DIGESTS
)

#: gcrypt digests that are not FIPS compliant
NONFIPS_GCRYPT_DIGESTS: Tuple[str, ...] = (
    "ripemd160",
    "tiger",
    "tiger2",
    "tiger192",
    "md4",
    "whirlpool",
    "gostr3411_94",
    "stribog256",
    "stribog512",
    "md5",
)

#: FIPS compliant gcrypt digests
FIPS_GCRYPT_DIGESTS: Tuple[str, ...] = (
    "sha224",
    "sha256",
    "sha384",
    "sha512",
    "sha3-224",
    "sha3-256",
    "sha3-384",
    "sha3-512",
)

if OS_VERSION != "15.3":
    FIPS_GCRYPT_DIGESTS += (
        "sha512_224",
        "sha512_256",
    )
    NONFIPS_GCRYPT_DIGESTS += ("sm3",)


# sha1 is non-FIPS in 15.6
if OS_VERSION == "15.6":
    NONFIPS_GCRYPT_DIGESTS += ("sha1",)
else:
    FIPS_GCRYPT_DIGESTS += ("sha1",)


def host_fips_enabled(fipsfile: str = "/proc/sys/crypto/fips_enabled") -> bool:
    """Returns a boolean indicating whether FIPS mode is enabled on this
    machine.

    Parameters:
    fipsfile: path to the file in :file:`/proc` determining whether FIPS mode is enabled

    """
    if not os.path.exists(fipsfile):
        return False

    with open(fipsfile, encoding="utf8") as fipsfile_fd:
        return fipsfile_fd.read().strip() == "1"


def target_fips_enforced() -> bool:
    """Returns a boolean indicating whether FIPS mode is enforced on this target."""
    return os.getenv("TARGET", "obs") in ("dso",)
