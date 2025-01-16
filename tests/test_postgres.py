"""Tests for the PostgreSQL related application container images."""

from datetime import timedelta
from itertools import product
from typing import List
from typing import Optional

import pg8000.dbapi
import pytest
from _pytest.mark import ParameterSet
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.runtime import LOCALHOST

from bci_tester.data import POSTGRESQL_CONTAINERS
from bci_tester.data import POSTGRES_PASSWORD

CONTAINER_IMAGES = POSTGRESQL_CONTAINERS


def test_entry_point(auto_container: ContainerData) -> None:
    """Verifies that the entrypoint of the image contains
    ``docker-entrypoint.sh``.

    """
    assert len(auto_container.inspect.config.entrypoint) == 1
    assert (
        "docker-entrypoint.sh" in auto_container.inspect.config.entrypoint[0]
    )


_OTHER_PG_USER = "foo"
_OTHER_PG_PW = "baz"
_POSTGRES_USER = "postgres"


def _generate_test_matrix() -> List[ParameterSet]:
    params = []

    for pg_cont in POSTGRESQL_CONTAINERS:
        marks = pg_cont.marks
        ports = pg_cont.forwarded_ports
        params.append(
            pytest.param(pg_cont, None, POSTGRES_PASSWORD, None, marks=marks)
        )

        for username, pg_user, pw in product(
            (None, _POSTGRES_USER),
            (None, _OTHER_PG_USER),
            (POSTGRES_PASSWORD, _OTHER_PG_PW),
        ):
            env = {"POSTGRES_PASSWORD": pw}
            if pg_user:
                env["POSTGRES_USER"] = pg_user

            params.append(
                pytest.param(
                    DerivedContainer(
                        base=pg_cont,
                        forwarded_ports=ports,
                        extra_environment_variables=env,
                        # don't use a Dockerfile to set USER, as buildah on RHEL
                        # 7 fails to create a container image with a
                        # healthcheck…
                        # so avoid an image build at all cost
                        extra_launch_args=(
                            ["--user", username] if username else []
                        ),
                        # https://github.com/SUSE/BCI-tests/issues/647
                        healthcheck_timeout=(
                            timedelta(minutes=6)
                            if LOCALHOST.system_info.arch == "ppc64le"
                            else None
                        ),
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
    pgdata = container_per_test.inspect.config.env["PGDATA"]
    pgdata_f = container_per_test.connection.file(pgdata)
    assert pgdata_f.exists
    assert pgdata_f.user == "postgres"
    assert pgdata_f.mode == 0o700

    assert container_per_test.connection.check_output("id -un") == (
        username or "root"
    )

    with pg8000.dbapi.connect(
        user=pg_user or "postgres",
        password=password,
        host="localhost",
        timeout=50,
        port=container_per_test.forwarded_ports[0].host_port,
    ) as conn:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);"
        )
        cur.execute(
            "INSERT INTO test (num, data) VALUES (%s, %s)",
            (100, "abc'def"),
        )

        cur.execute("SELECT * FROM test;")
        assert cur.fetchone() == [1, 100, "abc'def"]

        conn.commit()
