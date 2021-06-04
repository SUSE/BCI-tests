import pytest

from bci_tester.parse_data import build_containerlist, Container
from bci_tester.fips import host_fips_enabled, host_fips_supported
from bci_tester.trigger_test import RabbitMQConnection


def test_default_containerlist():
    # assert len makes sure we are reading the default file
    # to check for any eventual TypeErrors
    assert len(build_containerlist()) != 0


def test_buildcontainerlist(tmp_path):
    tmpfile = tmp_path / "temp.json"
    with open(tmpfile, "w") as fw:
        fw.write("{}")
    with pytest.raises(TypeError):
        build_containerlist(tmpfile)


def test_host_fips_supported(tmp_path):
    fipsfile = tmp_path / "fips"
    fipsfile.write_text("")
    assert host_fips_supported(f"{fipsfile}")


def test_host_fips_enabled(tmp_path):
    fipsfile = tmp_path / "fips"
    fipsfile.write_text("1")
    assert host_fips_enabled(f"{fipsfile}")


def test_host_fips_disabled(tmp_path):
    fipsfile = tmp_path / "fips"
    fipsfile.write_text("")
    assert not host_fips_enabled(f"{fipsfile}")


def test_routing_keys():
    con = RabbitMQConnection(message_topic_prefix="foo.bar")
    assert con.repository_routing_keys == [
        "foo.bar." + s for s in ("repo.publish_state", "repo.published")
    ]


def test_container_list():
    con = RabbitMQConnection(
        container_list=[
            Container(
                type="openjdk-devel",
                repo="devel/bci/images",
                image="bci/openjdk-devel",
                tag="16",
                version="16",
            ),
            Container(
                type="python",
                repo="home/fcrozat/matryoshka/containers_python36",
                image="python36",
                tag="latest",
                version="3.6",
            ),
            Container(
                type="node",
                repo="home/fcrozat/matryoshka/containers_node15",
                image="python15",
                tag="latest",
                version="15",
            ),
        ]
    )
    assert con.watched_projects["devel:bci"] == ["images"]
    assert con.watched_projects["home:fcrozat:matryoshka"] == [
        "containers_python36",
        "containers_node15",
    ]
    assert len(con.watched_projects) == 2
