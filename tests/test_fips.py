"""This module checks whether the container images run in FIPS mode on a host in
FIPS mode.

"""
import pytest
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import CONTAINERS_WITHOUT_ZYPPER
from bci_tester.data import OS_VERSION
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import NONFIPS_DIGESTS

assert (
    host_fips_enabled()
), "The host must run in FIPS mode for the FIPS test suite"


FIPS_ERR_MSG = (
    "not a known digest" if OS_VERSION == "15.3" else "Error setting digest"
)


@pytest.mark.parametrize(
    "container_per_test",
    CONTAINERS_WITH_ZYPPER
    + [
        pytest.param(
            *param.values,
            marks=list(param.marks)
            + [pytest.mark.xfail(reason="openssl is not installed")],
        )
        for param in CONTAINERS_WITHOUT_ZYPPER
    ],
    indirect=True,
)
def test_openssl_fips_hashes(container_per_test):
    """If the host is running in FIPS mode, then we check that all fips certified
    hash algorithms can be invoked via :command:`openssl $digest /dev/null` and
    all non-fips hash algorithms fail.

    """
    for digest in NONFIPS_DIGESTS:
        cmd = container_per_test.connection.run(f"openssl {digest} /dev/null")
        assert cmd.rc != 0
        assert FIPS_ERR_MSG in cmd.stderr

    for digest in FIPS_DIGESTS:
        dev_null_digest = container_per_test.connection.run_expect(
            [0], f"openssl {digest} /dev/null"
        ).stdout
        assert (
            f"{digest.upper()}(/dev/null)= " in dev_null_digest
        ), f"unexpected digest of hash {digest}: {dev_null_digest}"


@pytest.mark.parametrize(
    "container_per_test",
    CONTAINERS_WITH_ZYPPER
    + [
        pytest.param(
            *param.values,
            marks=list(param.marks)
            + [pytest.mark.xfail(reason="sysctl is not available")],
        )
        if param != BUSYBOX_CONTAINER
        else param
        for param in CONTAINERS_WITHOUT_ZYPPER
    ],
    indirect=True,
)
def test_fips_enabled_in_sysctl(container_per_test):
    """Run :command:`sysctl -a` and check in its output whether fips is
    enabled.

    """
    sysctl_output = container_per_test.connection.run_expect(
        [0], "sysctl -a"
    ).stdout
    assert "crypto.fips_enabled = 1" in sysctl_output
