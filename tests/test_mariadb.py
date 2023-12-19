"""Tests for the MariaDB related application container images."""
from itertools import product
from typing import List
from typing import Optional

import pymysql
import pytest
from _pytest.mark import ParameterSet
from pytest_container.container import container_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import MARIADB_CONTAINERS
from bci_tester.data import MARIADB_ROOT_PASSWORD


CONTAINER_IMAGES = MARIADB_CONTAINERS


def test_entry_point(auto_container: ContainerData) -> None:
    # do really nothing here, just check that the container launched
    assert auto_container.connection.run_expect([0], "ps")

    assert len(auto_container.inspect.config.entrypoint) == 1
    assert (
        "docker-entrypoint.sh" in auto_container.inspect.config.entrypoint[0]
    )


_other_db_user = "foo"
_other_db_pw = "baz"

# TODO test variants
_test_db = "bcitest"


def _generate_test_matrix() -> List[ParameterSet]:
    params = []

    for db_cont_param in MARIADB_CONTAINERS:
        db_cont = container_from_pytest_param(db_cont_param)
        marks = db_cont_param.marks
        ports = db_cont.forwarded_ports
        for db_user, db_pw in product(
            ("user", _other_db_user), (MARIADB_ROOT_PASSWORD, _other_db_pw)
        ):
            env = {
                "MARIADB_USER": db_user,
                "MARIADB_PASSWORD": db_pw,
                "MARIADB_DATABASE": _test_db,
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
            database=_test_db,
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
        database=_test_db,
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
