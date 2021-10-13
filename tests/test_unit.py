from bci_tester.fips import host_fips_enabled
from bci_tester.fips import host_fips_supported


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
