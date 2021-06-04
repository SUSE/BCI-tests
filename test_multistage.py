from dataclasses import dataclass
from os import path
from string import Template
from typing import Union

import pytest

from matryoshka_tester.helpers import GitRepositoryBuild
from matryoshka_tester.parse_data import containers, Container


@dataclass
class MultiStageBuild:
    builder: Container
    runner: Union[Container, str]

    dockerfile_template: str

    @property
    def dockerfile(self) -> str:
        builder = self.builder.url
        runner = (
            self.runner if isinstance(self.runner, str) else self.runner.url
        )

        return Template(self.dockerfile_template).substitute(
            builder=builder, runner=runner
        )


def get_container_by_type_tag(type: str, tag: str) -> Container:
    matching_containers = [
        c for c in containers if c.type == type and c.tag == tag
    ]
    assert len(matching_containers) == 1, (
        f"expected to find 1 container with the type {type} and tag {tag}, "
        f"but got {len(matching_containers)}"
    )
    return matching_containers[0]


OPENJDK_DEVEL_16 = get_container_by_type_tag("openjdk-devel", "16")
OPENJDK_16 = get_container_by_type_tag("openjdk", "16")
GOLANG_1_15 = get_container_by_type_tag("go", "1.15")


@pytest.mark.parametrize(
    "host_git_clone,multi_stage_build,retval,cmd_stdout",
    [
        pytest.param(
            GitRepositoryBuild(
                repository_url="https://github.com/toolbox4minecraft/amidst",
                repository_tag="v4.6",
            ),
            MultiStageBuild(
                OPENJDK_DEVEL_16,
                OPENJDK_16,
                """
FROM $builder as builder
WORKDIR /amidst
COPY ./amidst .
RUN mvn package -DskipTests=True

FROM $runner
WORKDIR /amidst/
COPY --from=builder /amidst/target .
CMD ["java", "-jar", "amidst-v4-6.jar"]
""",
            ),
            0,
            "[info] Amidst v4.6",
        ),
        pytest.param(
            GitRepositoryBuild(
                repository_url="https://github.com/apache/maven",
                repository_tag="maven-3.8.1",
            ),
            MultiStageBuild(
                OPENJDK_DEVEL_16,
                OPENJDK_DEVEL_16,
                """
FROM $builder as builder
WORKDIR /maven
COPY ./maven .
RUN mvn package && \
    zypper --non-interactive addrepo https://download.opensuse.org/repositories/Archiving/openSUSE_Leap_15.3/Archiving.repo && \
    zypper --non-interactive --gpg-auto-import-keys ref && \
    zypper --non-interactive in unzip && \
    unzip /maven/apache-maven/target/apache-maven-3.8.1-bin.zip

FROM $runner
WORKDIR /maven/
COPY --from=builder /maven/apache-maven-3.8.1/ .
CMD ["/maven/bin/mvn"]
""",
            ),
            1,
            "[ERROR] No goals have been specified for this build.",
        ),
        pytest.param(
            GitRepositoryBuild(
                repository_tag="v3.2.2",
                repository_url="https://gitlab.com/pdftk-java/pdftk.git",
            ),
            MultiStageBuild(
                OPENJDK_DEVEL_16,
                OPENJDK_16,
                """
FROM $builder as builder
WORKDIR /pdftk
COPY ./pdftk .
RUN zypper --non-interactive addrepo https://download.opensuse.org/repositories/Java:/packages/openSUSE_Leap_15.3/Java:packages.repo && \
    zypper --non-interactive --gpg-auto-import-keys ref && \
    zypper --non-interactive in apache-ant apache-ivy && \
    ant test-resolve && ant compile && ant jar

FROM $runner
WORKDIR /pdftk/
COPY --from=builder /pdftk/build/jar/pdftk.jar .
CMD ["java", "-jar", "pdftk.jar"]
""",
            ),
            0,
            """SYNOPSIS
       pdftk <input PDF files | - | PROMPT>
""",
        ),
        pytest.param(
            GitRepositoryBuild(
                repository_tag="0.10.2",
                repository_url="https://github.com/alexellis/k3sup",
            ),
            MultiStageBuild(
                GOLANG_1_15,
                "scratch",
                """
FROM $builder as builder
WORKDIR /k3sup
COPY ./k3sup .
RUN echo > ./hack/hashgen.sh && make all

FROM $runner
WORKDIR /k3sup
COPY --from=builder /k3sup/bin/k3sup .
CMD ["/k3sup/k3sup"]
""",
            ),
            0,
            'Use "k3sup [command] --help" for more information about a command.',
        ),
    ],
    indirect=["host_git_clone"],
)
def test_dockerfile_build(
    host,
    container_runtime,
    host_git_clone,
    multi_stage_build,
    retval,
    cmd_stdout,
):
    print(host_git_clone, multi_stage_build)
    tmp_path, build = host_git_clone

    with open(path.join(tmp_path, "Dockerfile"), "w") as dockerfile:
        dockerfile.write(multi_stage_build.dockerfile)

    cmd = host.run_expect([0], container_runtime.build_command)
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    assert (
        cmd_stdout
        in host.run_expect(
            [retval], f"{container_runtime.runner_binary} run --rm {img_id}"
        ).stdout
    )
