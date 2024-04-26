"""Tests for the tomcat containers."""
import pytest
import requests
import tenacity
from pytest_container import container_and_marks_from_pytest_param
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat

from bci_tester.data import TOMCAT_CONTAINERS


TOMCAT_WITH_SAMPLE = []

for tomcat_ctr in TOMCAT_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(tomcat_ctr)
    TOMCAT_WITH_SAMPLE.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                forwarded_ports=ctr.forwarded_ports,
                containerfile="""RUN cd $CATALINA_HOME/webapps; curl -sfO https://tomcat.apache.org/tomcat-10.1-doc/appdev/sample/sample.war
HEALTHCHECK --interval=5s --timeout=5s --retries=5 CMD ["/usr/bin/curl", "-sf", "http://localhost:8080/sample"]
""",
                image_format=ImageFormat.DOCKER,
            ),
            marks=marks,
        )
    )


@pytest.mark.parametrize("container", TOMCAT_CONTAINERS, indirect=True)
def test_tomcat_launches(container: ContainerData) -> None:
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
    baseurl = container.container.baseurl
    assert baseurl
    ver = baseurl.rpartition(":")[2]
    assert resp.status_code == 404
    assert f"Apache Tomcat/{ver}" in resp.text


@pytest.mark.parametrize(
    "container_per_test", TOMCAT_WITH_SAMPLE, indirect=True
)
def test_tomcat_launches_sample_app(container_per_test: ContainerData) -> None:
    """Launches a container derived from the tomcat containers that includes the
    `Tomcat sample application
    <https://tomcat.apache.org/tomcat-10.1-doc/appdev/sample/>`_ in the
    :file:`$CATALINA_HOME/webapps` directory. Tomcat should serve this sample
    app automatically via the `GET /sample` route. We test that Tomcat responds
    to `GET /sample` with a response containing `Sample "Hello, World"
    Application`.

    """
    resp = requests.get(
        f"http://localhost:{container_per_test.forwarded_ports[0].host_port}/sample",
        timeout=2,
    )
    assert resp.status_code == 200
    assert 'Sample "Hello, World" Application' in resp.text
