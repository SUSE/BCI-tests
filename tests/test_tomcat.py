import pytest
import requests
import tenacity
from pytest_container import container_and_marks_from_pytest_param
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat

from bci_tester.data import TOMCAT_10_CONTAINER
from bci_tester.data import TOMCAT_9_CONTAINER
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
    # no healthcheck possible, so we have to fallback to get + retry 🫣
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
    )
    def _fetch_tomcat_root() -> requests.Response:
        return requests.get(
            f"http://localhost:{container.forwarded_ports[0].host_port}"
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
    resp = requests.get(
        f"http://localhost:{container_per_test.forwarded_ports[0].host_port}/sample"
    )
    assert resp.status_code == 200
    assert 'Sample "Hello, World" Application' in resp.text


_params = []

for param, pkg_name in (
    (TOMCAT_9_CONTAINER, "tomcat"),
    (TOMCAT_10_CONTAINER, "tomcat10"),
):
    ctr, marks = container_and_marks_from_pytest_param(param)
    _params.append(
        pytest.param(
            DerivedContainer(base=ctr, extra_launch_args=["--user", "root"]),
            pkg_name,
            marks=marks,
        )
    )


@pytest.mark.parametrize(
    "container_per_test,pkg_name", _params, indirect=["container_per_test"]
)
def test_install_samples(
    container_per_test: ContainerData, pkg_name: str
) -> None:
    """Test that we can install the samples application packages:
    - ``
    """
    container_per_test.connection.check_output(
        f"zypper -n in {pkg_name}-webapps {pkg_name}-admin-webapps {pkg_name}-docs-webapp"
    )
