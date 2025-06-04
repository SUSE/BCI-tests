"""Tests for the MariaDB related application container images."""

import os
from itertools import product
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Union

import pymysql
import pytest
from _pytest.mark import ParameterSet
from pymysql.err import OperationalError
from pytest_container.container import BindMount
from pytest_container.container import ContainerData
from pytest_container.container import ContainerLauncher
from pytest_container.container import ContainerVolume
from pytest_container.container import DerivedContainer
from pytest_container.pod import Pod
from pytest_container.pod import PodData
from pytest_container.runtime import LOCALHOST
from pytest_container.runtime import OciRuntimeBase
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import MARIADB_CLIENT_CONTAINERS
from bci_tester.data import MARIADB_CONTAINERS
from bci_tester.data import MARIADB_ROOT_PASSWORD
from bci_tester.data import OS_VERSION
from bci_tester.runtime_choice import PODMAN_SELECTED

CONTAINER_IMAGES = MARIADB_CONTAINERS


assert isinstance(MARIADB_CONTAINERS[0], ParameterSet)


def test_entry_point(auto_container: ContainerData) -> None:
    """Verifies that the entrypoint of the image contains
    ``docker-entrypoint.sh``.

    """
    assert len(auto_container.inspect.config.entrypoint) == 1
    assert (
        "docker-entrypoint.sh" in auto_container.inspect.config.entrypoint[0]
    )


_OTHER_DB_USER = "foo"
_SOME_ROOT_PW = "'$ome; P@ssw0rd!>"
_OTHER_DB_PW = "baz"

# TODO test variants
_TEST_DB = "bcitest"


def _generate_test_matrix() -> List[ParameterSet]:
    params = []

    for db_cont in MARIADB_CONTAINERS:
        for db_user, db_pw, root_pw in product(
            ("user", _OTHER_DB_USER),
            (_SOME_ROOT_PW, _OTHER_DB_PW),
            (MARIADB_ROOT_PASSWORD, None),
        ):
            env = {
                "MARIADB_USER": db_user,
                "MARIADB_PASSWORD": db_pw,
                "MARIADB_DATABASE": _TEST_DB,
            }
            if root_pw:
                env["MARIADB_ROOT_PASSWORD"] = root_pw
            else:
                env["MARIADB_RANDOM_ROOT_PASSWORD"] = "1"

            params.append(
                pytest.param(
                    DerivedContainer(
                        base=db_cont,
                        forwarded_ports=db_cont.forwarded_ports,
                        extra_environment_variables=env,
                    ),
                    db_user,
                    db_pw,
                    root_pw,
                    marks=db_cont.marks,
                )
            )

    return params


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(
        8 if LOCALHOST.system_info.arch == "ppc64le" else 5
    ),
)
def _wait_for_server(connection):
    connection.check_output("healthcheck.sh --connect")


@pytest.mark.parametrize(
    "container_per_test,db_user,db_password,root_pw",
    _generate_test_matrix(),
    indirect=["container_per_test"],
)
def test_mariadb_db_env_vars(
    container_per_test: ContainerData,
    db_user: str,
    db_password: str,
    root_pw: Optional[str],
    container_runtime: OciRuntimeBase,
    host,
) -> None:
    """Simple smoke test connecting to the MariaDB database using the example
    from `<https://pymysql.readthedocs.io/en/latest/user/examples.html>`_ while
    setting the ``MARIADB_USER`` and ``MARIADB_PASSWORD`` environment
    variables.

    """
    dbdir = "/var/lib/mysql"

    dbdir_f = container_per_test.connection.file(dbdir)
    assert dbdir_f.exists
    # owner is root under docker and mysql under podman
    # assert dbdir_f.user == "mysql"
    assert dbdir_f.mode == 0o755

    assert container_per_test.connection.check_output("id -un") == ("root")

    _wait_for_server(container_per_test.connection)

    with pymysql.connect(
        user=db_user,
        password=db_password,
        database=_TEST_DB,
        host="127.0.0.1",
        port=container_per_test.forwarded_ports[0].host_port,
    ) as conn:
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

    if root_pw is None:
        for line in host.check_output(
            f"{container_runtime.runner_binary} logs {container_per_test.container_id}",
        ).splitlines():
            if "GENERATED ROOT PASSWORD: " in line:
                root_pw = line.partition("GENERATED ROOT PASSWORD: ")[
                    2
                ].strip()
                break
    assert root_pw, "Root password must be either set or obtained from the log"
    # Test that we can connect using the root password
    with pymysql.connect(
        user="root",
        password=root_pw,
        database=_TEST_DB,
        host="127.0.0.1",
        port=container_per_test.forwarded_ports[0].host_port,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            assert cur.fetchone() == (1,)

    # test that we can not connect using any other password
    with pytest.raises(OperationalError):
        pymysql.connect(
            user="root",
            password=root_pw[::-1],
            database=_TEST_DB,
            host="127.0.0.1",
            port=container_per_test.forwarded_ports[0].host_port,
        )


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
    Pod(
        containers=[
            client_db_cont,
            DerivedContainer(
                base=db_cont,
                extra_environment_variables={
                    "MARIADB_USER": _OTHER_DB_USER,
                    "MARIADB_PASSWORD": _OTHER_DB_PW,
                    "MARIADB_DATABASE": _TEST_DB,
                    "MARIADB_ROOT_PASSWORD": MARIADB_ROOT_PASSWORD,
                },
            ),
        ]
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
    server_con = pod_per_test.container_data[1].connection

    client_con.check_output("mariadb --version")

    _wait_for_server(server_con)

    mariadb_cmd = f"mariadb --user={_OTHER_DB_USER} --password={_OTHER_DB_PW} --host=0.0.0.0 {_TEST_DB}"

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


def test_mariadb_healthcheck_innodb_initialized(auto_container_per_test):
    """
    Test if InnoDB (storage engine) has completed initializing.

    See: `<https://mariadb.com/kb/en/using-healthcheck-sh/#-innodb_initialized>`_
    """
    conn = auto_container_per_test.connection

    _wait_for_server(conn)

    conn.check_output("healthcheck.sh --su-mysql --innodb_initialized")


def test_mariadb_healthcheck_galera_cluster_disabled(auto_container_per_test):
    """
    Ensure that Galera Cluster (multi-primary cluster) is disabled (experimental feature),
    i.e. :command:`healthcheck.sh --su-mysql --galera_online` fails.

    See: `<https://mariadb.com/kb/en/using-healthcheck-sh/#-galera_online>`_
    """
    conn = auto_container_per_test.connection

    _wait_for_server(conn)

    conn.run_expect([1], "healthcheck.sh --su-mysql --galera_online")


_DB_ENV = {
    "MARIADB_USER": _OTHER_DB_USER,
    "MARIADB_PASSWORD": _OTHER_DB_PW,
    "MARIADB_DATABASE": _TEST_DB,
    "MARIADB_ROOT_PASSWORD": MARIADB_ROOT_PASSWORD,
    "MARIADB_AUTO_UPGRADE": "1",
}


@pytest.mark.parametrize("ctr_image", MARIADB_CONTAINERS)
@pytest.mark.skipif(
    OS_VERSION not in ("15.6",),
    reason="MariaDB upgrade scenario not supported",
)
def test_mariadb_upgrade(
    container_runtime: OciRuntimeBase,
    pytestconfig: pytest.Config,
    ctr_image: DerivedContainer,
    tmp_path: Path,
    host,
) -> None:
    mounts: List[Union[BindMount, ContainerVolume]] = [
        BindMount(host_path=tmp_path, container_path="/var/lib/mysql")
    ]
    mariadb_old = DerivedContainer(
        base="registry.suse.com/suse/mariadb:10.6",
        containerfile='RUN set -euo pipefail; head -n -1 /usr/local/bin/gosu > /tmp/gosu;  echo \'exec setpriv --pdeathsig=keep --reuid="$u" --regid="$u" --clear-groups -- "$@"\' >> /tmp/gosu;  mv /tmp/gosu /usr/local/bin/gosu; chmod +x /usr/local/bin/gosu',
        volume_mounts=mounts,
        extra_environment_variables=_DB_ENV,
    )
    mariadb_new = DerivedContainer(
        base=ctr_image,
        volume_mounts=mounts,
        extra_environment_variables=_DB_ENV,
    )

    mariadb_cmd = f"mariadb --user={_OTHER_DB_USER} --password={_OTHER_DB_PW} --host=0.0.0.0 {_TEST_DB}"

    def _verify_rowcount(con: Any, table_name: str, no_of_rows: int):
        rows = (
            con.check_output(
                f'echo "SELECT count(*) FROM {table_name};" | {mariadb_cmd}'
            )
            .strip()
            .splitlines()
        )
        assert no_of_rows == int(rows[1])

    try:
        with ContainerLauncher.from_pytestconfig(
            mariadb_old, container_runtime, pytestconfig
        ) as launcher:
            launcher.launch_container()
            con = launcher.container_data.connection
            _wait_for_server(con)
            con.check_output(
                f'echo "CREATE TABLE random_strings (string VARCHAR(255) NOT NULL);" | {mariadb_cmd}'
            )

            for _ in range(10):
                con.check_output(
                    f"echo 'INSERT INTO random_strings (string) VALUES (MD5(RAND()));' | {mariadb_cmd}"
                )
            _verify_rowcount(con, "random_strings", 10)

            con.check_output(
                f'echo "CREATE TABLE random_numbers (number INT NOT NULL);" | {mariadb_cmd}'
            )
            for _ in range(12):
                con.check_output(
                    f"echo 'INSERT INTO random_numbers (number) VALUES (RAND());' | {mariadb_cmd}"
                )
            _verify_rowcount(con, "random_numbers", 12)

        with ContainerLauncher.from_pytestconfig(
            mariadb_new, container_runtime, pytestconfig
        ) as launcher:
            launcher.launch_container()
            con = launcher.container_data.connection
            _wait_for_server(con)
            _verify_rowcount(con, "random_strings", 10)
            _verify_rowcount(con, "random_numbers", 12)

    finally:
        # The tmp_path folder is chown'd to the mariadb user by the mariadb
        # container, podman remaps that to some subuid that our current user has
        # no permission to delete. With podman unshare we enter the user
        # namespace, where we can fix the file permissions so that the cleanup
        # by pytest works.
        # Note that we have to chown to root as root inside the user namespace
        # is our current user
        if PODMAN_SELECTED and os.getuid() != 0:
            host.check_output(f"podman unshare chown -R root:root {tmp_path}")
