"""This module checks whether the container images run in FIPS mode on a host in
FIPS mode.

"""

import os.path
import shutil

import pytest
from _pytest.config import Config
from _pytest.mark.structures import ParameterSet
from pytest_container.build import MultiStageBuild
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerData
from pytest_container.helpers import get_extra_build_args
from pytest_container.helpers import get_extra_run_args
from pytest_container.runtime import OciRuntimeBase

from bci_tester.data import ALL_CONTAINERS
from bci_tester.data import BASE_CONTAINER
from bci_tester.data import OS_VERSION
from bci_tester.data import LTSS_BASE_FIPS_CONTAINERS
from bci_tester.data import CONTAINERS_WITH_ZYPPER
from bci_tester.fips import FIPS_DIGESTS
from bci_tester.fips import host_fips_enabled
from bci_tester.fips import NONFIPS_DIGESTS


#: multistage :file:`Dockerfile` that builds the program from
#: :py:const:`FIPS_TEST_DOT_C` using gcc and copies it, ``libcrypto``, ``libssl``
#: and ``libz`` into the deployment image. The libraries must be copied, as they
#: are not available in the minimal container images.
DOCKERFILE = f"""FROM $builder as builder

WORKDIR /src/
COPY fips-test.c /src/
RUN zypper -n ref && zypper -n in gcc libopenssl-devel && zypper -n clean
RUN gcc -Og -g3 fips-test.c -Wall -Wextra -Wpedantic -lcrypto -lssl -o fips-test

FROM $runner

COPY --from=builder /src/fips-test /bin/fips-test
COPY --from=builder /usr/lib64/libcrypto.so.1.1 /usr/lib64/
COPY --from=builder /usr/lib64/libssl.so.1.1 /usr/lib64/
COPY --from=builder {'/usr' if OS_VERSION not in ('15.3', '15.4') else ''}/lib64/libz.so.1 /usr/lib64/
COPY --from=builder /usr/lib64/engines-1.1 /usr/lib64/engines-1.1
COPY --from=builder /usr/lib64/.libcrypto.so.1.1.hmac /usr/lib64/
COPY --from=builder /usr/lib64/.libssl.so.1.1.hmac /usr/lib64/

RUN /bin/fips-test sha256
"""

_non_fips_host_skip_mark = [
    pytest.mark.skipif(
        not host_fips_enabled(),
        reason="The target must run in FIPS mode for the FIPS test suite",
    )
]
CONTAINER_IMAGES = []
CONTAINER_IMAGES_WITH_ZYPPER = []
for target_list, param_list in (
    (CONTAINER_IMAGES, ALL_CONTAINERS),
    (CONTAINER_IMAGES_WITH_ZYPPER, CONTAINERS_WITH_ZYPPER),
):
    for param in param_list:
        ctr, marks = container_and_marks_from_pytest_param(param)
        if param in LTSS_BASE_FIPS_CONTAINERS:
            target_list.append(param)
        else:
            target_list.append(
                pytest.param(
                    ctr, marks=marks + _non_fips_host_skip_mark, id=param.id
                )
            )


@pytest.mark.parametrize("runner", CONTAINER_IMAGES)
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
        host.run_expect([0], f"{exec_cmd} /bin/fips-test {digest}")

    for digest in NONFIPS_DIGESTS:
        err_msg = host.run_expect(
            [1], f"{exec_cmd} /bin/fips-test {digest}"
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
        assert "is not a known digest" in cmd.stderr

    for digest in FIPS_DIGESTS:
        dev_null_digest = container_per_test.connection.check_output(
            f"openssl {digest} /dev/null"
        )
        assert (
            f"{digest.upper()}(/dev/null)= " in dev_null_digest
        ), f"unexpected digest of hash {digest}: {dev_null_digest}"


@pytest.mark.parametrize(
    "container_per_test", CONTAINER_IMAGES_WITH_ZYPPER, indirect=True
)
def test_openssl_fips_hashes(container_per_test: ContainerData):
    openssl_fips_hashes_test_fnct(container_per_test)
