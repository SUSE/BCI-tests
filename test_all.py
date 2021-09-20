from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import OS_PRETTY_NAME
from bci_tester.data import OS_VERSION

CONTAINER_IMAGES = ALL_CONTAINERS


def test_os_release(auto_container):
    assert auto_container.connection.file("/etc/os-release").exists

    for (var_name, value) in (
        ("VERSION_ID", OS_VERSION),
        ("PRETTY_NAME", OS_PRETTY_NAME),
    ):
        assert (
            auto_container.connection.run_expect(
                [0], f". /etc/os-release && echo ${var_name}"
            ).stdout.strip()
            == value
        )


def test_product(auto_container):
    assert auto_container.connection.file("/etc/products.d").is_directory
    assert auto_container.connection.file("/etc/products.d/SLES.prod").is_file
    assert auto_container.connection.file(
        "/etc/products.d/baseproduct"
    ).is_symlink
    assert (
        auto_container.connection.file("/etc/products.d/baseproduct").linked_to
        == "/etc/products.d/SLES.prod"
    )


def test_coreutils_present(auto_container):
    for binary in ("cat", "sh", "bash", "ls", "rm"):
        assert auto_container.connection.exists(binary)


def test_glibc_present(auto_container):
    for binary in ("ldconfig", "ldd"):
        assert auto_container.connection.exists(binary)
