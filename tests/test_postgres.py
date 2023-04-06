from itertools import product
from typing import List
from typing import Optional

import psycopg2
import pytest
from _pytest.mark import ParameterSet
from pytest_container.container import container_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.container import ImageFormat

from bci_tester.data import POSTGRES_PASSWORD
from bci_tester.data import POSTGRESQL_CONTAINERS


CONTAINER_IMAGES = POSTGRESQL_CONTAINERS


def test_entry_point(auto_container: ContainerData) -> None:
    # do really nothing here, just check that the container launched
    assert auto_container.connection.run_expect([0], "ps")

    assert len(auto_container.inspect.config.entrypoint) == 1
    assert (
        "docker-entrypoint.sh" in auto_container.inspect.config.entrypoint[0]
    )


_other_pg_user = "foo"
_other_pg_pw = "baz"
_postgres_user = "postgres"


def _generate_test_matrix() -> List[ParameterSet]:
    params = []

    for pg_cont_param in POSTGRESQL_CONTAINERS:
        pg_cont = container_from_pytest_param(pg_cont_param)
        marks = pg_cont_param.marks
        ports = pg_cont.forwarded_ports
        params.append(
            pytest.param(pg_cont, None, POSTGRES_PASSWORD, None, marks=marks)
        )

        for username, pg_user, pw in product(
            (None, _postgres_user),
            (None, _other_pg_user),
            (POSTGRES_PASSWORD, _other_pg_pw),
        ):
            env = {"POSTGRES_PASSWORD": pw}
            if pg_user:
                env["POSTGRES_USER"] = pg_user

            containerfile = ""
            if username:
                containerfile = f"USER {username}\n"

            params.append(
                pytest.param(
                    DerivedContainer(
                        base=pg_cont,
                        forwarded_ports=ports,
                        extra_environment_variables=env,
                        containerfile=containerfile,
                        image_format=ImageFormat.DOCKER,
                    ),
                    pg_user,
                    pw,
                    username,
                    marks=marks,
                )
            )

    return params


@pytest.mark.parametrize(
    "container_per_test,pg_user,password,username",
    _generate_test_matrix(),
    indirect=["container_per_test"],
)
def test_postgres_db_env_vars(
    container_per_test: ContainerData,
    pg_user: Optional[str],
    password: str,
    username: Optional[str],
) -> None:
    """Simple smoke test connecting to the PostgreSQL database using the example
    from `<https://www.psycopg.org/docs/usage.html#basic-module-usage>`_ while
    setting the ``POSTGRES_PASSWORD`` and ``POSTGRES_USER`` environment
    variables.

    """
    conn = None
    cur = None

    pgdata = container_per_test.inspect.config.env["PGDATA"]

    pgdata_f = container_per_test.connection.file(pgdata)
    assert pgdata_f.exists
    assert pgdata_f.user == "postgres"
    assert pgdata_f.mode == 0o700

    assert container_per_test.connection.run_expect(
        [0], "id -un"
    ).stdout.strip() == (username or "root")

    try:
        conn = psycopg2.connect(
            user=pg_user or "postgres",
            password=password,
            host="localhost",
            port=container_per_test.forwarded_ports[0].host_port,
        )
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);"
        )
        cur.execute(
            "INSERT INTO test (num, data) VALUES (%s, %s)", (100, "abc'def")
        )

        cur.execute("SELECT * FROM test;")
        assert cur.fetchone() == (1, 100, "abc'def")

        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
