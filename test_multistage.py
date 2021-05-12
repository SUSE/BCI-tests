from os import path
from shutil import copy

import pytest

from matryoshka_tester.helpers import GitRepositoryBuild


@pytest.mark.parametrize(
    "host_git_clone",
    (
        build.to_pytest_param()
        for build in (
            GitRepositoryBuild(
                repository_url="https://github.com/toolbox4minecraft/amidst",
                repository_tag="v4.6",
            ),
            GitRepositoryBuild(
                repository_url="https://github.com/apache/maven",
                repository_tag="maven-3.8.1",
                marks=pytest.mark.xfail(
                    reason="environment variables are not set correctly"
                ),
            ),
            GitRepositoryBuild(
                repository_tag="v3.2.2",
                repository_url="https://gitlab.com/pdftk-java/pdftk.git",
            ),
            GitRepositoryBuild(
                repository_tag="0.10.2",
                repository_url="https://github.com/alexellis/k3sup",
            ),
        )
    ),
    indirect=["host_git_clone"],
)
def test_dockerfile_build(host, container_runtime, host_git_clone):
    tmp_path, build = host_git_clone
    copy(
        path.join(
            path.dirname(__file__),
            "dockerfiles",
            build.repo_name,
        ),
        path.join(tmp_path, "Dockerfile"),
    )

    cmd = host.run_expect([0], container_runtime.build_command)
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    host.run_expect(
        [0], f"{container_runtime.runner_binary} run --rm {img_id}"
    )
