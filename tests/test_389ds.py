from bci_tester.data import CONTAINER_389DS
from pytest_container.runtime import LOCALHOST


CONTAINER_IMAGES = [CONTAINER_389DS]


def test_ldapwhoami(auto_container_per_test):
    auto_container_per_test.connection.run_expect(
        [0],
        "dsconf localhost backend create --suffix dc=example,dc=com --be-name userRoot",
    )

    auto_container_per_test.connection.run_expect(
        [0], "dsidm localhost initialise"
    )

    # Check a basic search
    auto_container_per_test.connection.run_expect(
        [0], "dsidm localhost account list"
    )

    # set a dummy password on an account
    auto_container_per_test.connection.run_expect(
        [0],
        "dsidm localhost account reset_password uid=demo_user,ou=people,dc=example,dc=com password",
    )

    # Unlock the account
    auto_container_per_test.connection.run_expect(
        [0],
        "dsidm localhost account unlock uid=demo_user,ou=people,dc=example,dc=com",
    )

    if LOCALHOST.exists("ldapwhoami"):
        assert (
            LOCALHOST.run_expect(
                [0],
                "ldapwhoami -H ldap://127.0.0.1:3389 -x -D 'uid=demo_user,ou=people,dc=example,dc=com' -w password",
            ).stdout.strip()
            == "dn: uid=demo_user,ou=people,dc=example,dc=com"
        )
