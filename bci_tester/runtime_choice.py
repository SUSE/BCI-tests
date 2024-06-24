from pytest_container import get_selected_runtime

#: Is :command:`docker` the selected runtime?
DOCKER_SELECTED: bool = False

#: Is :command:`podman` the selected runtime?
PODMAN_SELECTED: bool = False


try:
    runtime = get_selected_runtime()
    DOCKER_SELECTED = runtime.runner_binary == "docker"
    PODMAN_SELECTED = runtime.runner_binary == "podman"
except ValueError:
    # we are running without docker or podman and are probably just linting,
    # building the docs, etc.
    pass
