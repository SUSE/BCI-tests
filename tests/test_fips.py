"""This module checks whether the container images run in FIPS mode on a host in
FIPS mode.

"""

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import container_and_marks_from_pytest_param

from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import OS_VERSION
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import NONFIPS_DIGESTS
from bci_tester.fips import FIPS_GNUTLS_DIGESTS
from bci_tester.fips import NONFIPS_GNUTLS_DIGESTS
from bci_tester.fips import NULL_DIGESTS
from bci_tester.fips import host_fips_enabled

#: multistage :file:`Dockerfile` that builds the program from
#: :py:const:`FIPS_TEST_DOT_C` using gcc and copies it, ``libcrypto``, ``libssl``
#: and ``libz`` into the deployment image. The libraries must be copied, as they
#: are not available in the minimal container images.
DOCKERFILE = """WORKDIR /src/
COPY tests/files/fips-test.c /src/
RUN zypper -n ref && zypper -n in gcc libopenssl-devel && zypper -n clean
RUN gcc -Og -g3 fips-test.c -Wall -Wextra -Wpedantic -lcrypto -lssl -o fips-test
RUN mv fips-test /bin/fips-test

# smoke test
RUN /bin/fips-test sha256
"""

DOCKERFILE_GNUTLS = """WORKDIR /src/
COPY tests/files/fips-test-gnutls.c /src/
RUN zypper -n ref && zypper -n in gcc gnutls gnutls-devel && zypper -n clean
RUN gcc -Og -g3 fips-test-gnutls.c -Wall -Wextra -Wpedantic -lgnutls -o fips-test-gnutls
RUN mv fips-test-gnutls /bin/fips-test-gnutls

# smoke test
RUN /bin/fips-test-gnutls sha256
"""

_non_fips_host_skip_mark = [
    pytest.mark.skipif(
        not host_fips_enabled(),
        reason="The target must run in FIPS mode for the FIPS test suite",
    )
]

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
    )
    fips_gnutls_tester_ctr = DerivedContainer(
        base=ctr,
        containerfile=DOCKERFILE_GNUTLS,
        extra_environment_variables=ctr.extra_environment_variables,
        extra_launch_args=ctr.extra_launch_args,
        custom_entry_point=ctr.custom_entry_point,
    )
    if param in LTSS_BASE_FIPS_CONTAINERS:
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

    for digest in FIPS_DIGESTS:
        container_per_test.connection.check_output(f"/bin/fips-test {digest}")

    for digest in NONFIPS_DIGESTS:
        err_msg = container_per_test.connection.run_expect(
            [1], f"/bin/fips-test {digest}"
        ).stderr

        assert f"Unknown message digest {digest}" in err_msg


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

    for digest in FIPS_GNUTLS_DIGESTS:
        container_per_test.connection.check_output(f"/bin/fips-test-gnutls {digest}")

    for digest in NONFIPS_GNUTLS_DIGESTS:
        err_msg = container_per_test.connection.run_expect(
            [1], f"/bin/fips-test-gnutls {digest}"
        ).stderr

        assert f"Hash calculation failed" in err_msg, f"Hash calculation unexpectedly succeeded for {digest}"