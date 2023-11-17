"""This module checks whether the container images run in FIPS mode on a host in
FIPS mode.

"""
import os.path
import shutil
import sys

import pytest
from _pytest.config import Config
from _pytest.mark.structures import ParameterSet
from pytest_container import Version
from pytest_container.build import MultiStageBuild
from pytest_container.helpers import get_extra_build_args
from pytest_container.helpers import get_extra_run_args
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import OS_VERSION
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import NONFIPS_DIGESTS


#: Error message from OpenSSL when a non-FIPS digest is selected in FIPS mode
FIPS_ERR_MSG = (
    "not a known digest" if OS_VERSION == "15.3" else "Error setting digest"
)

pytestmark = pytest.mark.skipif(
    OS_VERSION == "tumbleweed",
    reason="no FIPS module in tumbleweed yet",
)

#: multistage :file:`Dockerfile` that builds the program from
#: :py:const:`FIPS_TEST_DOT_C` using gcc and copies it, ``libcrypto``, ``libssl``
#: and ``libz`` into the deployment image. The libraries must be copied, as they
#: are not available in the minimal container images.
DOCKERFILE = f"""FROM $builder as builder


WORKDIR /src/
COPY fips-test.c /src/
RUN zypper -n ref && zypper -n in gcc openssl libopenssl-devel && zypper -n clean
RUN gcc -O2 fips-test.c -Wall -Werror -lcrypto -lssl -o fips-test

FROM $runner

COPY --from=builder /src/fips-test /usr/local/bin/fips-test
COPY --from=builder /usr/bin/openssl /usr/bin/openssl
COPY --from=builder /usr/lib64/libcrypto.so.* /usr/lib64/
COPY --from=builder /usr/lib64/libssl.so.* /usr/lib64/
COPY --from=builder /usr/lib64/libz.so.1 /usr/lib64/
COPY --from=builder /usr/lib64/engines-* /usr/lib64/
COPY --from=builder /usr/lib64/.libcrypto.so.*.hmac /usr/lib64/
COPY --from=builder /usr/lib64/.libssl.so.*.hmac /usr/lib64/

RUN fips-test sha256
"""


@pytest.mark.parametrize("runner", ALL_CONTAINERS)
def test_openssl_binary(
    runner: ParameterSet,
    tmp_path,
    pytestconfig: Config,
    host,
    container_runtime: OciRuntimeBase,
):
    """Check that a binary linked against OpenSSL obeys the host's FIPS mode
    setting:

    - build a container image using :py:const:`DOCKERFILE`
    - run the bundled binary compiled from :file:`tests/files/fips-test.c` with
      all FIPS digests and assert that it successfully calculates the message
      digest
    - rerun the same binary with non-FIPS digests and assert that this fails
      with the expected error message.

    """
    multi_stage_build = MultiStageBuild(
        containers={"builder": BASE_CONTAINER, "runner": runner},
        containerfile_template=DOCKERFILE,
    )

    shutil.copy(
        os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "files", "fips-test.c"
        ),
        tmp_path / "fips-test.c",
    )

    img_id = multi_stage_build.build(
        tmp_path,
        pytestconfig,
        container_runtime,
        extra_build_args=get_extra_build_args(pytestconfig),
    )

    exec_cmd = " ".join(
        [container_runtime.runner_binary, "run", "--rm"]
        + get_extra_run_args(pytestconfig)
        + [img_id]
    )

    for digest in FIPS_DIGESTS:
        host.run_expect([0], f"{exec_cmd} fips-test {digest}")

    for digest in NONFIPS_DIGESTS:
        err_msg = host.run_expect([1], f"{exec_cmd} fips-test {digest}").stderr

        if Version.parse(OS_VERSION) <= Version(15, 5):
            assert f"Unknown message digest {digest}" in err_msg
        else:
            assert "disabled for FIPS" in err_msg


@pytest.mark.parametrize(
    "container_per_test", CONTAINERS_WITH_ZYPPER, indirect=True
)
def test_openssl_fips_hashes(container_per_test):
    """If the host is running in FIPS mode, then we check that all fips certified
    hash algorithms can be invoked via :command:`openssl $digest /dev/null` and
    all non-fips hash algorithms fail.

    """
    for digest in NONFIPS_DIGESTS:
        cmd = container_per_test.connection.run(
            f"env OPENSSL_FORCE_FIPS_MODE=1 openssl {digest} /dev/null"
        )
        assert cmd.rc != 0
        assert "is not a known digest" in cmd.stderr

    for digest in FIPS_DIGESTS:
        dev_null_digest = container_per_test.connection.check_output(
            f"env OPENSSL_FORCE_FIPS_MODE=1 openssl {digest} /dev/null"
        )
        assert (
            f"{digest.upper()}(/dev/null)= " in dev_null_digest
        ), f"unexpected digest of hash {digest}: {dev_null_digest}"
