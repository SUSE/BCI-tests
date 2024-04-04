"""Tests for the MariaDB related application container images."""
from itertools import product
from typing import List

import pymysql
import pytest
from _pytest.mark import ParameterSet
from pytest_container.container import container_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.pod import Pod
from pytest_container.pod import PodData
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import MARIADB_CLIENT_CONTAINERS
from bci_tester.data import MARIADB_CONTAINERS
from bci_tester.data import MARIADB_ROOT_PASSWORD


CONTAINER_IMAGES = MARIADB_CONTAINERS


def test_entry_point(auto_container: ContainerData) -> None:
    """Verifies that the entrypoint of the image contains
    ``docker-entrypoint.sh``.

    """
    assert len(auto_container.inspect.config.entrypoint) == 1
    assert (
        "docker-entrypoint.sh" in auto_container.inspect.config.entrypoint[0]
    )


_OTHER_DB_USER = "foo"
_OTHER_DB_PW = "baz"

# TODO test variants
_TEST_DB = "bcitest"


def _generate_test_matrix() -> List[ParameterSet]:
    params = []

    for db_cont_param in MARIADB_CONTAINERS:
        db_cont = container_from_pytest_param(db_cont_param)
        marks = db_cont_param.marks
        ports = db_cont.forwarded_ports
        for db_user, db_pw in product(
            ("user", _OTHER_DB_USER), (MARIADB_ROOT_PASSWORD, _OTHER_DB_PW)
        ):
            env = {
                "MARIADB_USER": db_user,
                "MARIADB_PASSWORD": db_pw,
                "MARIADB_DATABASE": _TEST_DB,
            }
            env["MARIADB_ROOT_PASSWORD"] = MARIADB_ROOT_PASSWORD
            ### not supported by the container
            # env["MARIADB_RANDOM_ROOT_PASSWORD"] = "1"

            params.append(
                pytest.param(
                    DerivedContainer(
                        base=db_cont,
                        forwarded_ports=ports,
                        extra_environment_variables=env,
                    ),
                    db_user,
                    db_pw,
                    marks=marks,
                )
            )

    return params


@pytest.mark.parametrize(
    "container_per_test,db_user,db_password",
    _generate_test_matrix(),
    indirect=["container_per_test"],
)
def test_mariadb_db_env_vars(
    container_per_test: ContainerData,
    db_user: str,
    db_password: str,
) -> None:
    """Simple smoke test connecting to the MariaDB database using the example
    from `<https://pymysql.readthedocs.io/en/latest/user/examples.html>`_ while
    setting the ``MARIADB_USER`` and ``MARIADB_PASSWORD`` environment
    variables.

    """
    conn = None
    cur = None

    dbdir = "/var/lib/mysql"

    dbdir_f = container_per_test.connection.file(dbdir)
    assert dbdir_f.exists
    # owner is root under docker and mysql under podman
    # assert dbdir_f.user == "mysql"
    assert dbdir_f.mode == 0o755

    assert container_per_test.connection.check_output("id -un") == ("root")

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def wait_for_db_to_start():
        conn = pymysql.connect(
            user=db_user,
            password=db_password,
            database=_TEST_DB,
            host="127.0.0.1",
            port=container_per_test.forwarded_ports[0].host_port,
        )
        with conn:
            conn.ping(reconnect=False)

    # no healthcheck - https://mariadb.org/mariadb-server-docker-official-images-healthcheck-without-mysqladmin/
    wait_for_db_to_start()

    conn = pymysql.connect(
        user=db_user,
        password=db_password,
        database=_TEST_DB,
        host="127.0.0.1",
        port=container_per_test.forwarded_ports[0].host_port,
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar(32));"
            )
            cur.execute(
                "INSERT INTO test (num, data) VALUES (%s, %s)",
                (100, "abc'def"),
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM test;")
            assert cur.fetchone() == (1, 100, "abc'def")


@pytest.mark.parametrize(
    "container_per_test",
    MARIADB_CLIENT_CONTAINERS,
    indirect=["container_per_test"],
)
def test_mariadb_client(container_per_test: ContainerData) -> None:
    """Smoke test of the MariaDB Client container, it verifies that the output
    of :command:`mysql --version` contains the string ``MariaDB``.

    """
    assert "MariaDB" in container_per_test.connection.check_output(
        "mysql --version"
    )


MARIADB_PODS = [
    pytest.param(
        Pod(
            containers=[
                container_from_pytest_param(client_db_cont),
                DerivedContainer(
                    base=container_from_pytest_param(db_cont),
                    extra_environment_variables={
                        "MARIADB_USER": _OTHER_DB_USER,
                        "MARIADB_PASSWORD": _OTHER_DB_PW,
                        "MARIADB_DATABASE": _TEST_DB,
                        "MARIADB_ROOT_PASSWORD": MARIADB_ROOT_PASSWORD,
                    },
                ),
            ]
        ),
        marks=[*db_cont.marks, *client_db_cont.marks],
    )
    for db_cont, client_db_cont in zip(
        MARIADB_CONTAINERS, MARIADB_CLIENT_CONTAINERS
    )
]


@pytest.mark.parametrize(
    "pod_per_test", MARIADB_PODS, indirect=["pod_per_test"]
)
def test_mariadb_client_in_pod(pod_per_test: PodData) -> None:
    """Simple test of the MariaDB Client container in a pod with the MariaDB
    container.

    The MariaDB Client container is used to connect to the MariaDB server in the
    MariaDB container. We then create a table, insert a value and check that we
    obtain the same values back via a ``SELECT``.

    """
    client_con = pod_per_test.container_data[0].connection
    client_con.check_output("mariadb --version")

    mariadb_cmd = f"mariadb --user={_OTHER_DB_USER} --password={_OTHER_DB_PW} --host=0.0.0.0 {_TEST_DB}"

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
    )
    def wait_for_server():
        client_con.check_output(mariadb_cmd)

    wait_for_server()

    client_con.check_output(
        f'echo "CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar(32));" | {mariadb_cmd}'
    )
    client_con.check_output(
        f"echo 'INSERT INTO test (num, data) VALUES (100, \"abcdef\")' | {mariadb_cmd}"
    )
    rows = (
        client_con.check_output(f'echo "SELECT * FROM test;" | {mariadb_cmd}')
        .strip()
        .splitlines()
    )

    assert rows and len(rows) == 2
    _, num, data = rows[-1].split()
    assert num == "100" and data == "abcdef"
