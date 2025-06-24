"""Tests for the Samba related application container images."""

from pathlib import Path

import pytest
from pytest_container.container import BindMount
from pytest_container.container import ContainerData
from pytest_container.container import DerivedContainer
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.pod import Pod
from pytest_container.pod import PodData
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from bci_tester.data import SAMBA_CLIENT_CONTAINERS
from bci_tester.data import SAMBA_SERVER_CONTAINERS
from bci_tester.data import SAMBA_TOOLBOX_CONTAINERS

CONTAINER_IMAGES = SAMBA_SERVER_CONTAINERS


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
)
def _wait_for_server(connection):
    connection.check_output("smbclient -L \\localhost -U % -m SMB3")


@pytest.mark.parametrize(
    "container_per_test",
    SAMBA_CLIENT_CONTAINERS,
    indirect=["container_per_test"],
)
def test_samba_client(container_per_test: ContainerData) -> None:
    """Smoke test for the Samba client container."""
    assert "Version 4." in container_per_test.connection.check_output(
        "smbclient --version"
    )


@pytest.mark.parametrize(
    "container_per_test",
    SAMBA_TOOLBOX_CONTAINERS,
    indirect=["container_per_test"],
)
def test_samba_toolbox(container_per_test: ContainerData) -> None:
    """Smoke test for the Samba toolbox container."""

    assert "Version 4." in container_per_test.connection.check_output(
        "smbclient --version"
    )

    assert "Version 4." in container_per_test.connection.check_output(
        "pdbedit --version"
    )


SAMBA_SERVER_TDBSAM_CONTAINERS = [
    pytest.param(
        DerivedContainer(
            base=container_and_marks_from_pytest_param(server_container)[0],
            singleton=True,
            volume_mounts=[
                BindMount(
                    host_path=str(
                        Path(__file__).parent / "files" / "smb.conf"
                    ),
                    container_path="/etc/samba/smb.conf",
                )
            ],
        ),
        marks=server_container.marks,
    )
    for server_container in SAMBA_SERVER_CONTAINERS
]


@pytest.mark.parametrize(
    "container_per_test",
    SAMBA_SERVER_TDBSAM_CONTAINERS,
    indirect=["container_per_test"],
)
def test_samba_server_tdbsam(container_per_test: ContainerData) -> None:
    """Smoke test for the Samba server container."""

    conn = container_per_test.connection

    _wait_for_server(conn)

    assert "Version 4." in conn.check_output("smbclient --version")

    # ensure that we can add user with home
    conn.check_output("smbuser -u dave -p password -d /shares/users/dave")

    # ensure that we can add user without home
    conn.check_output("smbuser -u bob -p password")

    # check that Dave can access his private home share
    conn.check_output(
        'smbclient //localhost/dave -U dave --password=password -c "dir"'
    )

    # check that Dave can write to his private home share
    conn.check_output(
        'echo "This is a test" > FILE.txt && smbclient //localhost/dave -U dave --password=password -c "put FILE.txt FILE.txt"'
    )


SAMBA_PODS = [
    pytest.param(
        Pod(
            containers=[
                container_and_marks_from_pytest_param(client_container)[0],
                DerivedContainer(
                    base=container_and_marks_from_pytest_param(
                        server_container
                    )[0],
                    singleton=True,
                    volume_mounts=[
                        BindMount(
                            host_path=str(
                                Path(__file__).parent / "files" / "smb.conf"
                            ),
                            container_path="/etc/samba/smb.conf",
                        )
                    ],
                ),
            ]
        ),
        marks=[*server_container.marks, *client_container.marks],
    )
    for server_container, client_container in zip(
        SAMBA_SERVER_CONTAINERS, SAMBA_CLIENT_CONTAINERS
    )
]


@pytest.mark.parametrize("pod_per_test", SAMBA_PODS, indirect=["pod_per_test"])
def test_samba_server_tdbsam_in_pod(pod_per_test: PodData) -> None:
    """
    Simple test for Samba containers where it tries to
    list and create files in the Samba share.
    """
    client_con = pod_per_test.container_data[0].connection
    server_con = pod_per_test.container_data[1].connection

    client_con.check_output("smbclient --version")

    _wait_for_server(server_con)

    # add a samba user to test authentication
    server_con.check_output(
        "smbuser -u dave -p password -d /shares/users/dave"
    )

    # check that we can connect to the samba server annonymously
    assert "public          Disk      Public files" in client_con.check_output(
        "smbclient -q -L //localhost -N"
    )

    # check that we can't see private shares
    assert (
        "dave            Disk      Home Directories"
        not in client_con.check_output("smbclient -q -L //localhost -N")
    )

    # check that we can't access a private share annonymously
    assert (
        "NT_STATUS_ACCESS_DENIED"
        in client_con.run_expect(
            [1], "smbclient //localhost/dave -N"
        ).stdout.strip()
    )

    # check that Dave can access his private home share
    client_con.check_output(
        'smbclient //localhost/dave -U dave --password=password -c "dir"'
    )

    # check that Dave can write to his private home share
    client_con.check_output(
        'echo "This is a test" > FILE.txt && smbclient //localhost/dave -U dave --password=password -c "put FILE.txt FILE.txt"'
    )
