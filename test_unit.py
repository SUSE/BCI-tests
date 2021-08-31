import pytest

from bci_tester.parse_data import build_containerlist, Container
from bci_tester.fips import host_fips_enabled, host_fips_supported

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
