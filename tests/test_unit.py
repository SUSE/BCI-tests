from bci_tester.fips import host_fips_enabled
from bci_tester.fips import host_fips_supported
from bci_tester.util import get_repos_from_zypper_xmlout


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


def test_repository_from_xml():
    repos = get_repos_from_zypper_xmlout(
        """<?xml version='1.0'?>
<stream>
<message type="info">Refreshing service &apos;container-suseconnect-zypp&apos;.</message>
<message type="error">Problem retrieving the repository index file for service &apos;container-suseconnect-zypp&apos;:
[container-suseconnect-zypp|file:/usr/lib/zypp/plugins/services/container-suseconnect-zypp]
</message>
<message type="warning">Skipping service &apos;container-suseconnect-zypp&apos; because of the above error.</message>
<repo-list>
<repo alias="SLE_BCI" name="SLE_BCI" type="rpm-md" priority="100" enabled="1" autorefresh="0" gpgcheck="1" repo_gpgcheck="1" pkg_gpgcheck="0">
<url>https://updates.suse.com/SUSE/Products/SLE-BCI/15-SP3/x86_64/product/</url>
</repo>
<repo alias="packages-microsoft-com-prod" name="packages-microsoft-com-prod" type="rpm-md" priority="99" enabled="1" autorefresh="0" gpgcheck="0" repo_gpgcheck="1" pkg_gpgcheck="1" raw_gpgcheck="1" gpgkey="https://packages.microsoft.com/keys/microsoft.asc">
<url>https://packages.microsoft.com/sles/15/prod/</url>
</repo>
</repo-list>
</stream>
"""
    )
    assert len(repos) == 2

    assert repos[0].name == "SLE_BCI"
    assert repos[0].alias == "SLE_BCI"
    assert repos[0].priority == 100
    assert repos[0].enabled
    assert repos[0].gpgcheck
    assert repos[0].repo_gpgcheck
    assert not repos[0].pkg_gpgcheck
    assert (
        repos[0].url
        == "https://updates.suse.com/SUSE/Products/SLE-BCI/15-SP3/x86_64/product/"
    )

    assert repos[1].name == "packages-microsoft-com-prod"
    assert repos[1].alias == "packages-microsoft-com-prod"
    assert repos[1].enabled
    assert not repos[1].gpgcheck
    assert repos[1].repo_gpgcheck
    assert repos[1].pkg_gpgcheck
    assert repos[1].url == "https://packages.microsoft.com/sles/15/prod/"
    assert repos[1].priority == 99
