import json

import pytest

from bci_tester.parse_data import containers


OS_PRETTY_NAME = "BCI 15.3"
VENDOR = "SUSE LLC"
URL = "https://www.suse.com/products/server/"


@pytest.mark.parametrize("container_data", [c for c in containers])
def test_metadata(container_data, host):
    res = host.run_expect([0], f"skopeo inspect docker://{container_data.url}")
    metadata = json.loads(res.stdout)

    assert metadata["Name"] == container_data.url.split(":")[0]

    labels = metadata["Labels"]

    for prefix in ("org.opensuse.bci", "org.opencontainers.image"):
        assert labels[f"{prefix}.vendor"] == VENDOR
        assert OS_PRETTY_NAME in labels[f"{prefix}.description"]
        assert OS_PRETTY_NAME in labels[f"{prefix}.title"]
        assert labels[f"{prefix}.url"] == URL

        if container_data.type not in ("base", "init"):
            assert labels[f"{prefix}.version"] == container_data.version
        else:
            assert "15.3" == labels[f"{prefix}.version"][:4]

    for prefix in ("org.opensuse.bci", "org.openbuildservice"):
        assert (
            "obs://build.opensuse.org/devel:BCI/"
            in labels[f"{prefix}.disturl"]
        )

    for prefix in (".bci", ""):
        reference = labels[f"org.opensuse{prefix}.reference"]
        if container_data.type not in ("base", "init"):
            assert reference == container_data.url.replace(
                "devel/bci/images/", ""
            )
        else:
            assert (
                container_data.url.replace("devel/bci/images/", "").split(":")[
                    0
                ]
                in reference
            )
