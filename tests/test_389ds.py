"""Basic tests for the 389-ds Application container image."""

from pytest_container.runtime import LOCALHOST

from bci_tester.data import CONTAINER_389DS_CONTAINERS


CONTAINER_IMAGES = CONTAINER_389DS_CONTAINERS


def test_ldapwhoami(auto_container_per_test):
    basedn = "dc=suse,dc=com"
    auto_container_per_test.connection.check_output(
        f"dsconf localhost backend create --suffix {basedn} --be-name userroot --create-suffix --create-entries",
    )

    # Check a basic search
    auto_container_per_test.connection.check_output(
        f"dsidm -b {basedn} localhost account list"
    )

    # set a dummy password on an account
    auto_container_per_test.connection.check_output(
        f"dsidm -b {basedn} localhost account reset_password uid=demo_user,ou=people,{basedn} password",
    )

    # Unlock the account
    auto_container_per_test.connection.check_output(
        f"dsidm -b {basedn} localhost account unlock uid=demo_user,ou=people,{basedn}",
    )

    host_port = auto_container_per_test.forwarded_ports[0].host_port
    if LOCALHOST.exists("ldapwhoami"):
        assert (
            LOCALHOST.check_output(
                f"ldapwhoami -H ldap://127.0.0.1:{host_port} -x -D 'uid=demo_user,ou=people,{basedn}' -w password",
            )
            == f"dn: uid=demo_user,ou=people,{basedn}"
        )
