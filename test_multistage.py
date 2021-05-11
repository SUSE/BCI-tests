import pytest

from matryoshka_tester.helpers import ContainerBuild


@pytest.mark.parametrize(
    "dockerfile_build",
    (
        build.to_pytest_param()
        for build in (
            ContainerBuild(
                name="amidst",
                pre_build_steps=(
                    "git clone -b v4.6 "
                    "https://github.com/toolbox4minecraft/amidst"
                ),
            ),
            ContainerBuild(
                name="maven",
                pre_build_steps=(
                    "git clone -b maven-3.8.1 https://github.com/apache/maven"
                ),
                marks=pytest.mark.xfail(
                    reason="environment variables are not set correctly"
                ),
            ),
            ContainerBuild(
                name="pdftk",
                pre_build_steps=(
                    "git clone -b v3.2.2 "
                    "https://gitlab.com/pdftk-java/pdftk.git"
                ),
            ),
            ContainerBuild(
                name="k3sup",
                pre_build_steps=(
                    "git clone -b 0.10.2 https://github.com/alexellis/k3sup"
                ),
            ),
        )
    ),
    indirect=["dockerfile_build"],
)
def test_dockerfile_build(host, container_runtime, dockerfile_build):
    cmd = host.run_expect([0], container_runtime.build_command)
    img_id = container_runtime.get_image_id_from_stdout(cmd.stdout)

    host.run_expect(
        [0], f"{container_runtime.runner_binary} run --rm {img_id}"
    )
