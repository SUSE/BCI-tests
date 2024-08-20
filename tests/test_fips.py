"""This module checks whether the container images run in FIPS mode on a host in
FIPS mode.

"""

from pathlib import Path

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import BindMount
from pytest_container.container import ContainerData
from pytest_container.container import container_and_marks_from_pytest_param

from bci_tester.data import BASE_FIPS_CONTAINERS
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import OS_VERSION
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import FIPS_GNUTLS_DIGESTS
from bci_tester.fips import NONFIPS_DIGESTS
from bci_tester.fips import NONFIPS_GNUTLS_DIGESTS
from bci_tester.fips import NULL_DIGESTS
from bci_tester.fips import host_fips_enabled

#: multistage :file:`Dockerfile` that builds the program from
#: :py:const:`FIPS_TEST_DOT_C` using gcc and copies it, ``libcrypto``, ``libssl``
#: and ``libz`` into the deployment image. The libraries must be copied, as they
#: are not available in the minimal container images.
DOCKERFILE = """WORKDIR /src/
COPY tests/files/fips-test.c /src/
"""

DOCKERFILE_GNUTLS = """WORKDIR /src/
COPY tests/files/fips-test-gnutls.c /src/
"""

_non_fips_host_skip_mark = [
    pytest.mark.skipif(
        not host_fips_enabled(),
        reason="The target must run in FIPS mode for the FIPS test suite",
    )
]

_zypp_credentials_dir: str = "/etc/zypp/credentials.d"

CONTAINER_IMAGES_WITH_ZYPPER = []
FIPS_TESTER_IMAGES = []
FIPS_GNUTLS_TESTER_IMAGES = []
for param in CONTAINERS_WITH_ZYPPER:
    ctr, marks = container_and_marks_from_pytest_param(param)
    fips_tester_ctr = DerivedContainer(
        base=ctr,
        containerfile=DOCKERFILE,
        extra_environment_variables=ctr.extra_environment_variables,
        extra_launch_args=ctr.extra_launch_args,
        custom_entry_point=ctr.custom_entry_point,
        volume_mounts=(
            [
                BindMount(
                    _zypp_credentials_dir,
                    host_path=_zypp_credentials_dir,
                )
            ]
            if Path(_zypp_credentials_dir).exists()
            else []
        ),
    )
    fips_gnutls_tester_ctr = DerivedContainer(
        base=ctr,
        containerfile=DOCKERFILE_GNUTLS,
        extra_environment_variables=ctr.extra_environment_variables,
        extra_launch_args=ctr.extra_launch_args,
        custom_entry_point=ctr.custom_entry_point,
        volume_mounts=(
            [
                BindMount(
                    _zypp_credentials_dir,
                    host_path=_zypp_credentials_dir,
                )
            ]
            if Path(_zypp_credentials_dir).exists()
            else []
        ),
    )
    if param in LTSS_BASE_FIPS_CONTAINERS + BASE_FIPS_CONTAINERS:
        CONTAINER_IMAGES_WITH_ZYPPER.append(param)
        FIPS_TESTER_IMAGES.append(
            pytest.param(fips_tester_ctr, marks=marks, id=param.id)
        )
        FIPS_GNUTLS_TESTER_IMAGES.append(
            pytest.param(fips_gnutls_tester_ctr, marks=marks, id=param.id)
        )
    else:
        CONTAINER_IMAGES_WITH_ZYPPER.append(
            pytest.param(
                ctr, marks=marks + _non_fips_host_skip_mark, id=param.id
            )
        )
        FIPS_TESTER_IMAGES.append(
            pytest.param(
                fips_tester_ctr,
                marks=marks + _non_fips_host_skip_mark,
                id=param.id,
            )
        )
        FIPS_GNUTLS_TESTER_IMAGES.append(
            pytest.param(
                fips_gnutls_tester_ctr,
                marks=marks + _non_fips_host_skip_mark,
                id=param.id,
            )
        )


@pytest.mark.parametrize(
    "container_per_test", FIPS_TESTER_IMAGES, indirect=True
)
def test_openssl_binary(container_per_test: ContainerData) -> None:
    """Check that a binary linked against OpenSSL obeys the host's FIPS mode
    setting:

    - build a container image using :py:const:`DOCKERFILE`
    - run the bundled binary compiled from :file:`tests/files/fips-test.c` with
      all FIPS digests and assert that it successfully calculates the message
      digest
    - rerun the same binary with non-FIPS digests and assert that this fails
      with the expected error message.

    """
    container_per_test.connection.check_output(
        "zypper --gpg-auto-import-keys -n ref && zypper -n in gcc libopenssl-devel && zypper -n clean &&"
        "gcc -O2 fips-test.c -Wall -Wextra -Wpedantic -lcrypto -lssl -o fips-test && "
        "mv fips-test /bin/fips-test"
    )

    for digest in FIPS_DIGESTS:
        container_per_test.connection.check_output(f"/bin/fips-test {digest}")

    for digest in NONFIPS_DIGESTS:
        err_msg = container_per_test.connection.run_expect(
            [1], f"/bin/fips-test {digest}"
        ).stderr

        assert (
            f"Unknown message digest {digest}" in err_msg
            or "EVP_DigestInit_ex was not successful" in err_msg
        ), f"non-fips digest {digest} unexpected output {err_msg}"


def openssl_fips_hashes_test_fnct(container_per_test: ContainerData) -> None:
    """If the host is running in FIPS mode, then we check that all fips certified
    hash algorithms can be invoked via :command:`openssl $digest /dev/null` and
    all non-fips hash algorithms fail.

    """
    for digest in NONFIPS_DIGESTS:
        cmd = container_per_test.connection.run(f"openssl {digest} /dev/null")
        assert cmd.rc != 0
        assert (
            "is not a known digest" in cmd.stderr
            or "Error setting digest" in cmd.stderr
        )

    for digest in FIPS_DIGESTS:
        dev_null_digest = container_per_test.connection.check_output(
            f"openssl {digest} /dev/null"
        )
        assert (
            f"= {NULL_DIGESTS[digest]}" in dev_null_digest
        ), f"unexpected digest of hash {digest}: {dev_null_digest}"


@pytest.mark.skipif(
    OS_VERSION in ("15.3",), reason="FIPS 140-3 not supported on 15.3"
)
def fips_mode_setup_check(container_per_test: ContainerData) -> None:
    """If the host is running in FIPS mode, then `fips-mode-setup --check` should
    exit with `0`.

    """
    container_per_test.connection.check_output("fips-mode-setup --check")


@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_WITH_ZYPPER, indirect=True
)
def test_openssl_fips_hashes(container_per_test: ContainerData):
    openssl_fips_hashes_test_fnct(container_per_test)


@pytest.mark.parametrize(
    "container_per_test", FIPS_GNUTLS_TESTER_IMAGES, indirect=True
)
def test_gnutls_binary(container_per_test: ContainerData) -> None:
    """Check that a binary linked against Gnutls obeys the host's FIPS mode
    setting:

    - build a container image using :py:const:`DOCKERFILE_GNUTLS`
    - run the bundled binary compiled from :file:`tests/files/fips-gnutls-test.c` with
      all FIPS digests and assert that it successfully calculates the message
      digest
    - rerun the same binary with non-FIPS digests and assert that this fails
      with the expected error message.

    """

    container_per_test.connection.check_output(
        "ls /usr/lib64/libgnutl* && "
        "rpm -q libgnutls-devel && "
        "zypper --gpg-auto-import-keys -n ref && zypper -n in gcc gnutls gnutls-devel && zypper -n clean && "
        "gcc -Og -g3 fips-test-gnutls.c -Wall -Wextra -Wpedantic -lgnutls -o fips-test-gnutls && "
        "mv fips-test-gnutls /bin/fips-test-gnutls"
    )

    expected_fips_gnutls_digests = {
        "md5": "bcfe53d9a81f2d0382a280d017796084e59ff97941044f85df5297e1c302d260",
        "sha1": "c87d25a09584c040f3bfc53b570199591deb10ba648a6a6ffffdaa0badb23b8baf90b6168dd16b3a",
        "sha224": "54655eae3d97147de34564572231c34d6d0917dd7852b5b93647fb4fe53ee97e5e0a2a4d359b5b461409dc44d9315afbc3b7d6bc5cd598e6",
        "sha256": "4ea6a95a3a56fa6b7c1673c145198c52265fea4fe4cebef97249b39c25a733a0d2a84f4b8b650937ec8f73cd8be2c74add5a911ba64df27458ed8229da804a26",
        "sha384": "416b69644f4844065fcfe7b60f14fe07d1573420c4db2b15a6d1f4cb2b6933ffce8dcb1bce7788b962eb3d0c8d4eefc4acbfd470c22c0d95a1d10a087dc31988b9f7bfeb13be70b876a73558be664e5858d11f9459923e6e5fd838cb5708b969",
        "sha512": "3916af571551c0c40eb19936c7ac2c090e140cad48e348dc4e9d5b6508a34ac6090daeeed3a081ce0e44c90b181987b71f09e8e0c190e5af26cd46eea724489de1c112ff908febc3b98b1693a6cd3564eaf8e5e6ca629d084d9f0eba99247cacdd72e369ff8941397c2807409ff66be64be908da17ad7b8a49a2a26c0e8086aa",
    }

    for digest in FIPS_GNUTLS_DIGESTS:
        container_per_test.connection.check_output(
            f"/bin/fips-test-gnutls {digest}"
        )
        res = container_per_test.connection.check_output(
            f"/bin/fips-test-gnutls {digest}"
        )
        assert expected_fips_gnutls_digests[digest] in res

    for digest in NONFIPS_GNUTLS_DIGESTS:
        err_msg = container_per_test.connection.run_expect(
            [1], f"/bin/fips-test-gnutls {digest}"
        ).stderr

        assert (
            "Hash calculation failed" in err_msg
        ), f"Hash calculation unexpectedly succeeded for {digest}"
