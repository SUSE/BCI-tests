"""Tests for the tomcat containers."""

## Maintainer: BCI team (#proj-bci)

from pathlib import Path

import pytest
import requests
import tenacity
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData

from bci_tester.data import TOMCAT_CONTAINERS


def _tomcat_launch_test_fn(container: ContainerData) -> requests.Response:
    """Simple smoke test verifying that the entrypoint launches tomcat and the
    server is responding to a ``GET /`` on the exposed port.

    """

    # no healthcheck possible, so we have to fallback to get + retry 🫣
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
    )
    def _fetch_tomcat_root() -> requests.Response:
        return requests.get(
            f"http://localhost:{container.forwarded_ports[0].host_port}",
            timeout=2,
        )

    resp = _fetch_tomcat_root()
    return resp


@pytest.mark.parametrize("container", TOMCAT_CONTAINERS, indirect=True)
def test_tomcat_launches(container: ContainerData) -> None:
    """Simple smoke test verifying that the entrypoint launches tomcat and the
    server is responding to a ``GET /`` on the exposed port.

    """

    resp = _tomcat_launch_test_fn(container)

    baseurl = container.container.baseurl
    assert baseurl
    ver = baseurl.rpartition(":")[2].partition("-")[0]
    assert resp.status_code == 404
    assert f"Apache Tomcat/{ver}" in resp.text


@pytest.mark.parametrize("container", TOMCAT_CONTAINERS, indirect=True)
def test_tomcat_logs(container: ContainerData) -> None:
    """"""
    _tomcat_launch_test_fn(container)
    logs = container.read_container_logs()
    assert (
        "[main] org.apache.catalina.startup.Catalina.start Server startup in"
        in logs
    ), "startup logging message not found"
    assert (
        "-Djava.util.logging.config.file=/usr/share/tomcat/conf/logging.properties"
        in logs
    ), "expected logfile CLI argument not found"


@pytest.mark.parametrize(
    "container_per_test", TOMCAT_CONTAINERS, indirect=True
)
def test_tomcat_launches_sample_app(
    container_per_test: ContainerData,
    host,
    tmp_path: Path,
    container_runtime: OciRuntimeBase,
) -> None:
    """Launches a tomcat container. The test downloads the `Tomcat sample
    application <https://tomcat.apache.org/tomcat-10.1-doc/appdev/sample/>`_ and
    copies it into the :file:`$CATALINA_HOME/webapps` directory, which then
    tomcat should serve automatically via the `GET /sample` route. We test that
    Tomcat responds to `GET /sample` with a response containing ``Sample "Hello,
    World" Application``.

    """

    sample_req = requests.get(
        "https://tomcat.apache.org/tomcat-10.1-doc/appdev/sample/sample.war"
    )
    sample_req.raise_for_status()

    sample_war_dest = str(tmp_path / "sample.war")
    with open(sample_war_dest, "wb") as sample_war:
        for chunk in sample_req.iter_content():
            sample_war.write(chunk)

    host.check_output(
        f"{container_runtime.runner_binary} cp {sample_war_dest} {container_per_test.container_id}:/srv/tomcat/webapps/"
    )

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
    )
    def _fetch_tomcat_sample() -> requests.Response:
        return requests.get(
            f"http://localhost:{container_per_test.forwarded_ports[0].host_port}/sample",
            timeout=2,
        )

    resp = _fetch_tomcat_sample()
    assert resp.status_code == 200
    assert 'Sample "Hello, World" Application' in resp.text
