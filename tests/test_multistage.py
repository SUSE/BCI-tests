"""Integration tests via multistage container builds."""

from typing import Optional

import pytest
from pytest_container import container_and_marks_from_pytest_param
from pytest_container.container import ContainerImageData
from pytest_container.container import MultiStageContainer
from pytest_container.runtime import LOCALHOST

from bci_tester.data import GOLANG_CONTAINERS
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_21_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_21_CONTAINER
from bci_tester.data import OS_VERSION


def _clone_cmd(repo_url: str, tag: Optional[str] = None) -> str:
    res = "git clone --depth 1 "
    if tag:
        res += f"--branch {tag} "
    return res + repo_url


#: maven version that is being build in the multistage test build
MAVEN_VERSION = "3.9.9"

#: Dockerfile template to build `amidst
#: <https://github.com/toolbox4minecraft/amidst>`_
AMIDST_DOCKERFILE = f"""FROM $builder as builder
RUN {_clone_cmd('https://github.com/toolbox4minecraft/amidst', 'v4.7')} /amidst
WORKDIR /amidst
RUN mvn package -DskipTests=True

FROM $runner
WORKDIR /amidst/
COPY --from=builder /amidst/target .
CMD ["java", "-jar", "amidst-v4-7.jar"]
"""

#: template of a Dockerfile to build maven in the OpenJDK devel container and
#: copy it into the OpenJDK base container
MAVEN_BUILD_DOCKERFILE = f"""FROM $builder as builder
RUN {_clone_cmd('https://github.com/apache/maven', 'maven-' + MAVEN_VERSION)} /maven
WORKDIR /maven
RUN mvn package && zypper -n in unzip && \
    unzip /maven/apache-maven/target/apache-maven-{MAVEN_VERSION}-bin.zip

FROM $runner
WORKDIR /maven/
COPY --from=builder /maven/apache-maven-{MAVEN_VERSION}/ .
CMD ["/maven/bin/mvn"]
"""

#: Dockerfile to build pdftk in the openjdk devel container and transfer it into
#: the openjdk container.
PDFTK_BUILD_DOCKERFILE = f"""FROM $builder as builder
RUN {_clone_cmd('https://gitlab.com/pdftk-java/pdftk.git', 'v3.3.3')} /pdftk
WORKDIR /pdftk
RUN zypper -n in apache-ant apache-ivy && ant test-resolve && ant compile && ant jar

FROM $runner
WORKDIR /pdftk/
COPY --from=builder /pdftk/build/jar/pdftk.jar .
CMD ["java", "-jar", "pdftk.jar"]
"""


#: dockerfile template to build k3sup in the go
#: container and transfer it into a scratch container
K3SUP_DOCKERFILE = f"""FROM $builder as builder
RUN {_clone_cmd('https://github.com/alexellis/k3sup', '0.13.7')} /k3sup
WORKDIR /k3sup
RUN echo > ./hack/hashgen.sh && make all

FROM $runner
WORKDIR /k3sup
COPY --from=builder /k3sup/bin/k3sup .
CMD ["/k3sup/k3sup"]
"""


OPENJDK_DEVEL_CONTAINER = OPENJDK_DEVEL_11_CONTAINER
if OS_VERSION in ("15.6",):
    OPENJDK_DEVEL_CONTAINER = OPENJDK_DEVEL_21_CONTAINER

OPENJDK_CONTAINER = OPENJDK_11_CONTAINER
if OS_VERSION in ("15.6",):
    OPENJDK_CONTAINER = OPENJDK_21_CONTAINER

_jdk_devel_ctr, _jdk_devel_marks = container_and_marks_from_pytest_param(
    OPENJDK_DEVEL_CONTAINER
)
_jdk_ctr, _jdk_marks = container_and_marks_from_pytest_param(OPENJDK_CONTAINER)


@pytest.mark.parametrize(
    "container_image, retval, expected_stdout",
    [
        pytest.param(
            MultiStageContainer(
                containers={
                    "builder": _jdk_devel_ctr,
                    "runner": _jdk_ctr,
                },
                containerfile=AMIDST_DOCKERFILE,
            ),
            0,
            "[info] Amidst v4.7",
            marks=_jdk_marks + _jdk_devel_marks,
        ),
        pytest.param(
            MultiStageContainer(
                containers={"builder": _jdk_devel_ctr, "runner": _jdk_ctr},
                containerfile=PDFTK_BUILD_DOCKERFILE,
            ),
            0,
            """SYNOPSIS
       pdftk <input PDF files | - | PROMPT>""",
            marks=_jdk_marks + _jdk_devel_marks,
        ),
        pytest.param(
            MultiStageContainer(
                containers={
                    "builder": _jdk_devel_ctr,
                    "runner": _jdk_devel_ctr,
                },
                containerfile=MAVEN_BUILD_DOCKERFILE,
            ),
            1,
            "No goals have been specified for this build.",
            marks=_jdk_devel_marks,
        ),
    ]
    + [
        pytest.param(
            MultiStageContainer(
                containers={
                    "builder": container_and_marks_from_pytest_param(param)[0],
                    "runner": "scratch",
                },
                containerfile=K3SUP_DOCKERFILE,
            ),
            0,
            'Use "k3sup [command] --help" for more information about a command.',
            marks=[
                pytest.mark.xfail(
                    condition=LOCALHOST.system_info.arch != "x86_64",
                    reason="Currently broken on arch != x86_64, see https://github.com/alexellis/k3sup/pull/345",
                )
            ]
            + param.marks,
        )
        for param in GOLANG_CONTAINERS
    ],
    indirect=["container_image"],
)
def test_multistage_build(
    container_image: ContainerImageData,
    retval: int,
    expected_stdout: str,
    host,
) -> None:
    """Integration test of multistage container builds. We fetch a project
    (optionally checking out a specific tag), run a two stage build using a
    dockerfile template where we substitute the ``$runner`` and ``$builder``
    containers for the supplied images. Finally we run the ``$runner`` and
    verify the return value and standard output.

    .. list-table::
       :header-rows: 1

       * - project and tag
         - :file:`Dockerfile`
         - ``builder``
         - ``runner``
         - return value
         - standard output

       * - `<https://github.com/toolbox4minecraft/amidst>`_ at ``v4.7``
         - :py:const:`AMIDST_DOCKERFILE`
         - OpenJDK devel
         - OpenJDK
         - ``0``
         - ``[info] Amidst v4.7``

       * - `<https://github.com/apache/maven>`_ at ``maven-`` +
           :py:const:`MAVEN_VERSION`
         - :py:const:`MAVEN_BUILD_DOCKERFILE`
         - OpenJDK devel
         - OpenJDK
         - ``1``
         - ``No goals have been specified for this build.``

       * - `<https://gitlab.com/pdftk-java/pdftk.git>`_ at ``v3.3.1``
         - :py:const:`PDFTK_BUILD_DOCKERFILE`
         - OpenJDK devel
         - OpenJDK
         - ``0``
         - ``SYNOPSIS       pdftk <input PDF files | - | PROMPT>``

       * - `<https://github.com/alexellis/k3sup>`_ at ``0.11.1``
         - :py:const:`K3SUP_DOCKERFILE`
         - Go
         - scratch
         - ``0``
         - ``Use "k3sup [command] --help" for more information about a command.``

    """

    assert expected_stdout in host.run_expect(
        [retval], container_image.run_command
    ).stdout.replace("\r", "")
