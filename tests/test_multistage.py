"""Integration tests via multistage container builds."""
import pytest
from _pytest.config import Config
from bci_tester.data import DOTNET_ASPNET_5_0_CONTAINER
from bci_tester.data import DOTNET_SDK_5_0_CONTAINER
from bci_tester.data import GO_1_16_CONTAINER
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER
from pytest_container import get_extra_build_args
from pytest_container import get_extra_run_args
from pytest_container import GitRepositoryBuild
from pytest_container import MultiStageBuild
from pytest_container.runtime import LOCALHOST

from bci_tester.data import DOTNET_ASPNET_5_0_CONTAINER
from bci_tester.data import DOTNET_SDK_5_0_CONTAINER
from bci_tester.data import GO_1_16_CONTAINER
from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_DEVEL_11_CONTAINER


#: maven version that is being build in the multistage test build
MAVEN_VERSION = "3.8.3"

#: Dockerfile template to build `amidst
#: <https://github.com/toolbox4minecraft/amidst>`_
AMIDST_DOCKERFILE = """FROM $builder as builder
WORKDIR /amidst
COPY ./amidst .
RUN mvn package -DskipTests=True
FROM $runner
WORKDIR /amidst/
COPY --from=builder /amidst/target .
CMD ["java", "-jar", "amidst-v4-7.jar"]
"""

#: template of a Dockerfile to build maven in the OpenJDK devel container and
#: copy it into the OpenJDK base container
MAVEN_BUILD_DOCKERFILE = f"""FROM $builder as builder
WORKDIR /maven
COPY ./maven .
RUN mvn package && zypper -n in unzip && \
    unzip /maven/apache-maven/target/apache-maven-{MAVEN_VERSION}-bin.zip
FROM $runner
WORKDIR /maven/
COPY --from=builder /maven/apache-maven-{MAVEN_VERSION}/ .
CMD ["/maven/bin/mvn"]
"""

#: Dockerfile to build pdftk in the openjdk devel container and transfer it into
#: the openjdk container.
PDFTK_BUILD_DOCKERFILE = """FROM $builder as builder
WORKDIR /pdftk
COPY ./pdftk .
RUN zypper -n in apache-ant apache-ivy && ant test-resolve && ant compile && ant jar

FROM $runner
WORKDIR /pdftk/
COPY --from=builder /pdftk/build/jar/pdftk.jar .
CMD ["java", "-jar", "pdftk.jar"]
"""


#: dockerfile template to build k3sup in the go
#: container and transfer it into a scratch container
K3SUP_DOCKERFILE = """FROM $builder as builder
WORKDIR /k3sup
COPY ./k3sup .
RUN zypper -n in make && echo > ./hack/hashgen.sh && make all

FROM $runner
WORKDIR /k3sup
COPY --from=builder /k3sup/bin/k3sup .
CMD ["/k3sup/k3sup"]
"""

#: modified version of upstream's `Dockerfile
#: <https://github.com/phillipsj/adventureworks-k8s-sample/blob/main/Dockerfile>`_:
#:
#: - the ``entrypoint.sh`` is custom, so that the application terminates
#: - the docker build is not run from the repos top level dir, but one directory
#:   "above"
DOTNET_K8S_SAMPLE_DOCKERFILE = r"""FROM $builder AS build
WORKDIR /src

COPY ./adventureworks-k8s-sample/AdventureWorks.sln AdventureWorks.sln
COPY ./adventureworks-k8s-sample/AdventureWorks.App/*.csproj ./AdventureWorks.App/
COPY ./adventureworks-k8s-sample/BlazorLeaflet/*.csproj ./BlazorLeaflet/
RUN dotnet restore AdventureWorks.sln

COPY ./adventureworks-k8s-sample/AdventureWorks.App/. ./AdventureWorks.App/
COPY ./adventureworks-k8s-sample/BlazorLeaflet/. ./BlazorLeaflet/

RUN dotnet publish -c release -o /app --no-restore

FROM $runner
WORKDIR /app
COPY --from=build /app ./
RUN zypper -n in curl
RUN echo $$'#!/bin/bash -e \n\
dotnet AdventureWorks.App.dll & \n\
c=0 \n\
until curl localhost:5000 >/dev/null ; do \n\
  ((c++)) && ((c==20)) && ( \n\
    curl localhost:5000|grep Adventure \n\
    exit 1 \n\
  ) \n\
  sleep 1 \n\
done \n\
pkill dotnet \n\
' > entrypoint.sh && chmod +x entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
"""


@pytest.mark.parametrize(
    "host_git_clone,multi_stage_build,retval,cmd_stdout",
    [
        (
            GitRepositoryBuild(
                repository_url="https://github.com/toolbox4minecraft/amidst",
                repository_tag="v4.7",
            ),
            MultiStageBuild(
                containers={
                    "builder": OPENJDK_DEVEL_11_CONTAINER,
                    "runner": OPENJDK_11_CONTAINER,
                },
                containerfile_template=AMIDST_DOCKERFILE,
            ),
            0,
            "[info] Amidst v4.7",
        ),
        (
            GitRepositoryBuild(
                repository_url="https://github.com/apache/maven",
                repository_tag=f"maven-{MAVEN_VERSION}",
            ),
            MultiStageBuild(
                containers={
                    "builder": OPENJDK_DEVEL_11_CONTAINER,
                    "runner": OPENJDK_DEVEL_11_CONTAINER,
                },
                containerfile_template=MAVEN_BUILD_DOCKERFILE,
            ),
            1,
            "[ERROR] No goals have been specified for this build.",
        ),
        (
            GitRepositoryBuild(
                repository_tag="v3.3.1",
                repository_url="https://gitlab.com/pdftk-java/pdftk.git",
            ),
            MultiStageBuild(
                containers={
                    "builder": OPENJDK_DEVEL_11_CONTAINER,
                    "runner": OPENJDK_11_CONTAINER,
                },
                containerfile_template=PDFTK_BUILD_DOCKERFILE,
            ),
            0,
            """SYNOPSIS
       pdftk <input PDF files | - | PROMPT>
        """,
        ),
        pytest.param(
            GitRepositoryBuild(
                repository_tag="0.11.1",
                repository_url="https://github.com/alexellis/k3sup",
            ),
            MultiStageBuild(
                containers={"builder": GO_1_16_CONTAINER, "runner": "scratch"},
                containerfile_template=K3SUP_DOCKERFILE,
            ),
            0,
            'Use "k3sup [command] --help" for more information about a command.',
            marks=pytest.mark.xfail(
                condition=LOCALHOST.system_info.arch != "x86_64",
                reason="Currently broken on arch != x86_64, see https://github.com/alexellis/k3sup/pull/345",
            ),
        ),
        pytest.param(
            GitRepositoryBuild(
                repository_url="https://github.com/phillipsj/adventureworks-k8s-sample.git"
            ),
            MultiStageBuild(
                containers={
                    "builder": DOTNET_SDK_5_0_CONTAINER,
                    "runner": DOTNET_ASPNET_5_0_CONTAINER,
                },
                containerfile_template=DOTNET_K8S_SAMPLE_DOCKERFILE,
            ),
            0,
            """Microsoft.Hosting.Lifetime[0]\n      Now listening on: http://localhost:5000
\x1b[40m\x1b[32minfo\x1b[39m\x1b[22m\x1b[49m: Microsoft.Hosting.Lifetime[0]
      Application started. Press Ctrl+C to shut down.
\x1b[40m\x1b[32minfo\x1b[39m\x1b[22m\x1b[49m: Microsoft.Hosting.Lifetime[0]
      Hosting environment: Production
\x1b[40m\x1b[32minfo\x1b[39m\x1b[22m\x1b[49m: Microsoft.Hosting.Lifetime[0]
      Content root path: /app
""",
            marks=pytest.mark.skipif(
                LOCALHOST.system_info.arch != "x86_64",
                reason="The dotnet containers are only available for x86_64",
            ),
        ),
    ],
    indirect=["host_git_clone"],
)
def test_dockerfile_build(
    host,
    container_runtime,
    host_git_clone,
    multi_stage_build: MultiStageBuild,
    retval: int,
    cmd_stdout: str,
    pytestconfig: Config,
):
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
         - ``[ERROR] No goals have been specified for this build.``

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

       * - `<https://github.com/phillipsj/adventureworks-k8s-sample.git>`_
         - :py:const:`DOTNET_K8S_SAMPLE_DOCKERFILE`
         - .Net 5.0
         - ASP.Net 5.0
         - ``0``
         - `omitted`
    """
    tmp_path, _ = host_git_clone

    multi_stage_build.prepare_build(tmp_path, pytestconfig.rootpath)

    cmd = host.run_expect(
        [0],
        f"{' '.join(container_runtime.build_command + get_extra_build_args(pytestconfig))} {tmp_path}",
    )
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    assert (
        cmd_stdout
        in host.run_expect(
            [retval],
            f"{container_runtime.runner_binary} run --rm {' '.join(get_extra_run_args(pytestconfig))}{img_id}",
        ).stdout
    )
