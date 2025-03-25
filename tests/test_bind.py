from datetime import timedelta
from pathlib import Path
from typing import Dict
from typing import Optional

import dns.query
import pytest
from dns import message
from dns import name
from dns import rdatatype
from dns import resolver
from dns.rrset import RRset
from pytest_container import BindMount
from pytest_container import DerivedContainer
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.container import EntrypointSelection

from bci_tester.data import BIND_CONTAINERS

CONTAINER_IMAGES = BIND_CONTAINERS


def _make_dns_request(
    port: int,
    domain: str = "suse.com",
    record_type: rdatatype.RdataType = rdatatype.RdataType.A,
    dns_server: str = "127.0.0.1",
) -> message.Message:
    query = message.make_query(name.from_text(domain), record_type)
    return dns.query.udp(query, dns_server, port=port)


@pytest.mark.parametrize(
    "record_type",
    (
        rdatatype.RdataType.A,
        rdatatype.RdataType.AAAA,
        rdatatype.RdataType.MX,
    ),
)
def test_basic_resolution(
    auto_container: ContainerData, record_type: rdatatype.RdataType
) -> None:
    """Test that the bind9 in the container responds with the same DNS records
    for the ``suse.com`` domain for the ``A``, ``AAAA`` and ``MX`` records.

    """
    domain = "suse.com"
    resp = _make_dns_request(
        port=auto_container.forwarded_ports[0].host_port,
        record_type=record_type,
    )

    assert resp
    assert resp.answer

    def find_record_in_answer(
        answer: resolver.Answer | RRset,
    ) -> Optional[str]:
        for rdata in answer:
            if rdata.rdtype == record_type:
                return str(rdata)

        return None

    record = None
    for answer in resp.answer:
        record = find_record_in_answer(answer)
        if record:
            break

    assert record, f"No valid {record_type} record obtained from bind"

    expected_resp = find_record_in_answer(
        resolver.Resolver().resolve(domain, record_type)
    )
    assert expected_resp, (
        f"Did not obtain a {record_type} for {domain} from the default resolver"
    )

    assert record == expected_resp, (
        f"Expect {expected_resp} from bind, but got {record}"
    )


def test_env_variables_from_sysconfig_set(
    auto_container: ContainerData,
) -> None:
    """Smoke test checking that the container environment contains by default
    the same values as set via sourcing :file:`/etc/sysconfig/name`.

    """

    def env_to_dict(env_stdout: str) -> Dict[str, str]:
        """Converts the output of :command:`env` into a dictionary of
        environment variable names as the key and their values as the value.

        """
        res = {}
        for line in env_stdout.strip().splitlines():
            var, _, value = line.strip().partition("=")
            res[var] = value
        return res

    env: str = auto_container.connection.check_output("env")

    env_with_source: str = auto_container.connection.check_output(
        "source /etc/sysconfig/named && env"
    )

    assert env_to_dict(env) == env_to_dict(env_with_source)


_BIND_WITH_CUSTOM_CONF = []
for param in BIND_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(param)
    _NAMED_CONF = "/etc/bind/named.conf"
    _BIND_WITH_CUSTOM_CONF.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                extra_environment_variables={"NAMED_CONF": _NAMED_CONF},
                volume_mounts=[
                    BindMount(
                        container_path=_NAMED_CONF,
                        host_path=str(
                            Path(__file__).parent / "files" / "named.conf"
                        ),
                    ),
                    BindMount(
                        container_path="/etc/bind/db.blocked",
                        host_path=str(
                            Path(__file__).parent / "files" / "db.blocked"
                        ),
                    ),
                ],
                forwarded_ports=ctr.forwarded_ports,
            ),
            marks=marks,
        )
    )


@pytest.mark.parametrize("container", _BIND_WITH_CUSTOM_CONF, indirect=True)
def test_custom_named_config(container: ContainerData) -> None:
    """Verify that we can supply a custom :file:`named.conf` via the environment
    variable ``NAMED_CONF``.

    For that we utilize a custom named config that blocks google.com and passes
    requests for suse.com. We verify that we loaded the correct config by
    performing a DNS query for both domains and asserting that we get an answer
    for suse.com and none for google.com

    """
    port = container.forwarded_ports[0].host_port
    resp = _make_dns_request(port)

    assert resp.answer

    empty_resp = _make_dns_request(port, domain="google.com")
    assert not empty_resp.answer


_BIND_WITH_CUSTOM_CHECKER = []
_CHECKER_TOUCHED_FILE = "/tmp/check-conf-worked"
for param in BIND_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(param)

    _BIND_WITH_CUSTOM_CHECKER.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                extra_environment_variables={
                    "NAMED_CHECKCONF_BIN": "/usr/bin/touch",
                    "NAMED_CHECKCONF_ARGS": _CHECKER_TOUCHED_FILE,
                },
            ),
            marks=marks,
        )
    )


@pytest.mark.parametrize("container", _BIND_WITH_CUSTOM_CHECKER, indirect=True)
def test_custom_checker(container: ContainerData) -> None:
    """Test that we can supply a custom checker via ``NAMED_CHECKCONF_BIN`` and
    the binary is actually run in the entrypoint.

    For this, we supply :command:`touch` as the checker and pass it a file. Once
    the container launched, we check that the file exists.

    """
    assert container.connection.file(_CHECKER_TOUCHED_FILE).exists


_BIND_WITH_BASH = []
for param in BIND_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(param)

    _BIND_WITH_BASH.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                # don't launch bind as it chown's /var/lib/named
                entry_point=EntrypointSelection.BASH,
                # ignore healthcheck, bind is not running in this container
                healthcheck_timeout=timedelta(seconds=-1),
            ),
            marks=marks,
        )
    )


@pytest.mark.parametrize("container", _BIND_WITH_BASH, indirect=True)
def test_tmpfiles_d_created(container: ContainerData) -> None:
    """Check that our container image has all directories and files that
    would've been created by systemd-tmpfiles.

    """
    tmpfiles_d = container.connection.file(
        "/usr/lib/tmpfiles.d/bind.conf"
    ).content_string

    for line in tmpfiles_d.strip().splitlines():
        if line.startswith("#"):
            continue

        tp, path, mode, owner, group, age, arg = line.split()

        # sanity check, we don't handle these below at all
        assert age == "-" and arg == "-"

        # another sanity check because we don't test other tmpfiles.d constructs
        assert tp in ("d", "C")

        # directories
        if tp == "d":
            dir = container.connection.file(path)
            assert dir.exists
            assert dir.is_directory
            assert dir.user == owner
            assert dir.group == group
            assert oct(dir.mode) == f"0o{mode}"

        # created files
        elif tp == "C":
            file = container.connection.file(path)
            assert file.exists
            assert file.is_file
            assert owner == "-" and group == "-" and mode == "-"
