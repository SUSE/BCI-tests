"""Basic tests for the 389-ds Application container image."""

from typing import List

import pytest
from _pytest.mark import ParameterSet
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.runtime import LOCALHOST

from bci_tester.data import CONTAINER_389DS_CONTAINERS


def _generate_test_matrix() -> List[ParameterSet]:
    params = []
    for ds_cont_param in CONTAINER_389DS_CONTAINERS:
        ds_cont = container_and_marks_from_pytest_param(ds_cont_param)[0]
        marks = ds_cont_param.marks
        ports = ds_cont.forwarded_ports
        # add param to test as a root user
        params.append(pytest.param(ds_cont, marks=marks))

        # add param to test as a non root user
        params.append(
            pytest.param(
                DerivedContainer(
                    base=ds_cont,
                    forwarded_ports=ports,
                    extra_launch_args=(["--user", "dirsrv"]),
                ),
                marks=marks,
            )
        )

    return params


@pytest.mark.parametrize(
    "container_per_test",
    _generate_test_matrix(),
    indirect=["container_per_test"],
)
def test_ldapwhoami(
    container_per_test: ContainerData,
):
    basedn = "dc=suse,dc=com"
    container_per_test.connection.check_output(
        f"dsconf localhost backend create --suffix {basedn} --be-name userroot --create-suffix --create-entries",
    )

    # Check a basic search
    container_per_test.connection.check_output(
        f"dsidm -b {basedn} localhost account list"
    )

    # set a dummy password on an account
    container_per_test.connection.check_output(
        f"dsidm -b {basedn} localhost account reset_password uid=demo_user,ou=people,{basedn} password",
    )

    # Unlock the account
    container_per_test.connection.check_output(
        f"dsidm -b {basedn} localhost account unlock uid=demo_user,ou=people,{basedn}",
    )

    host_port = container_per_test.forwarded_ports[0].host_port
    if LOCALHOST.exists("ldapwhoami"):
        assert (
            LOCALHOST.check_output(
                f"ldapwhoami -H ldap://127.0.0.1:{host_port} -x -D 'uid=demo_user,ou=people,{basedn}' -w password",
            )
            == f"dn: uid=demo_user,ou=people,{basedn}"
        )
