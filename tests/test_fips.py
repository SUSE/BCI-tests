"""This module checks whether the container images run in FIPS mode on a host in
FIPS mode.

"""
import os.path
import shutil
import sys

import pytest
from _pytest.config import Config
from _pytest.mark.structures import ParameterSet
from pytest_container.build import MultiStageBuild
from pytest_container.helpers import get_extra_build_args
from pytest_container.helpers import get_extra_run_args
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import BUSYBOX_CONTAINER
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.data import CONTAINERS_WITHOUT_ZYPPER
from bci_tester.data import OS_VERSION
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import NONFIPS_DIGESTS


# building the documentation will fail on a non-FIPS host otherwise
if "sphinx" not in sys.modules:
    assert (
        host_fips_enabled()
    ), "The host must run in FIPS mode for the FIPS test suite"


#: Error message from OpenSSL when a non-FIPS digest is selected in FIPS mode
FIPS_ERR_MSG = (
    "not a known digest" if OS_VERSION == "15.3" else "Error setting digest"
)


#: multistage :file:`Dockerfile` that builds the program from
#: :py:const:`FIPS_TEST_DOT_C` using gcc and copies it, ``libcrypto``, ``libssl``
#: and ``libz`` into the deployment image. The libraries must be copied, as they
#: are not available in the minimal container images.
DOCKERFILE = """FROM $builder as builder

WORKDIR /src/
COPY fips-test.c /src/
RUN zypper -n ref && zypper -n in gcc libopenssl-devel && zypper -n clean
RUN gcc -Og -g3 fips-test.c -Wall -Wextra -Wpedantic -lcrypto -lssl -o fips-test

FROM $runner

COPY --from=builder /src/fips-test /bin/fips-test
COPY --from=builder /usr/lib64/libcrypto.so.1.1 /usr/lib64/
COPY --from=builder /usr/lib64/libssl.so.1.1 /usr/lib64/
COPY --from=builder /lib64/libz.so.1 /usr/lib64/
COPY --from=builder /usr/lib64/engines-1.1 /usr/lib64/engines-1.1
COPY --from=builder /usr/lib64/.libcrypto.so.1.1.hmac /usr/lib64/
COPY --from=builder /usr/lib64/.libssl.so.1.1.hmac /usr/lib64/

RUN /bin/fips-test sha256
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
    multi_stage_build.prepare_build(tmp_path, pytestconfig.rootpath)

    shutil.copy(
        os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "files", "fips-test.c"
        ),
        tmp_path / "fips-test.c",
    )

    cmd = host.run_expect(
        [0],
        " ".join(
            container_runtime.build_command
            + get_extra_build_args(pytestconfig)
            + [str(tmp_path)]
        ),
    )
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    exec_cmd = " ".join(
        [container_runtime.runner_binary, " run --rm -it "]
        + get_extra_run_args(pytestconfig)
        + [img_id]
    )

    for digest in FIPS_DIGESTS:
        host.run_expect([0], f"{exec_cmd} /bin/fips-test {digest}")

    for digest in NONFIPS_DIGESTS:
        assert (
            f"Unknown message digest {digest}"
            in host.run_expect(
                [1], f"{exec_cmd} /bin/fips-test {digest}"
            ).stdout
        )


@pytest.mark.parametrize(
    "container_per_test",
    CONTAINERS_WITH_ZYPPER
    + [
        pytest.param(
            *param.values,
            marks=list(param.marks)
            + [pytest.mark.xfail(reason="openssl is not installed")],
        )
        for param in CONTAINERS_WITHOUT_ZYPPER
    ],
    indirect=True,
)
def test_openssl_fips_hashes(container_per_test):
    """If the host is running in FIPS mode, then we check that all fips certified
    hash algorithms can be invoked via :command:`openssl $digest /dev/null` and
    all non-fips hash algorithms fail.

    """
    for digest in NONFIPS_DIGESTS:
        cmd = container_per_test.connection.run(f"openssl {digest} /dev/null")
        assert cmd.rc != 0
        assert FIPS_ERR_MSG in cmd.stderr

    for digest in FIPS_DIGESTS:
        dev_null_digest = container_per_test.connection.run_expect(
            [0], f"openssl {digest} /dev/null"
        ).stdout
        assert (
            f"{digest.upper()}(/dev/null)= " in dev_null_digest
        ), f"unexpected digest of hash {digest}: {dev_null_digest}"


@pytest.mark.parametrize(
    "container_per_test",
    CONTAINERS_WITH_ZYPPER
    + [
        pytest.param(
            *param.values,
            marks=list(param.marks)
            + [pytest.mark.xfail(reason="sysctl is not available")],
        )
        if param != BUSYBOX_CONTAINER
        else param
        for param in CONTAINERS_WITHOUT_ZYPPER
    ],
    indirect=True,
)
def test_fips_enabled_in_sysctl(container_per_test):
    """Run :command:`sysctl -a` and check in its output whether fips is
    enabled.

    """
    sysctl_output = container_per_test.connection.run_expect(
        [0], "sysctl -a"
    ).stdout
    assert "crypto.fips_enabled = 1" in sysctl_output
