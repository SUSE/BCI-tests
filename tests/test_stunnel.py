"""Test module for the stunnel container image.

Stunnel requires a certificate to create TLS connections. We create a self
signed certificate for that in the :file:`tests/files/stunnel/` directory as
follows:

.. code-block:: shell-session

   $ openssl genrsa -out server.key 2048
   $ openssl req -new -key server.key -out server.csr
   $ openssl x509 -req -days 3650 -in server.csr -signkey server.key -out server.crt -extfile v3.ext

The :command:`openssl req` call will ask for some input, you may provide it with
any content that you like.

.. warning::

   The self signed certificate will expire in December 2034. If you're still
   using it and tests start to fail, that's why.

"""

import ssl
from pathlib import Path

import pytest
import requests
import tenacity
from pytest_container import BindMount
from pytest_container import DerivedContainer
from pytest_container import PortForwarding
from pytest_container.container import ContainerData
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import STUNNEL_CONTAINER

_stunnel_kwargs = STUNNEL_CONTAINER.dict()
for key in [
    "custom_entry_point",
    "extra_environment_variables",
    "containerfile",
    "forwarded_ports",
]:
    _stunnel_kwargs.pop(key)

_cert_dir = Path(__file__).parent / "files" / "stunnel"
_SERVER_CRT = str(_cert_dir / "server.crt")

_stunnel_kwargs["volume_mounts"].extend(
    [
        BindMount(
            container_path="/etc/stunnel/stunnel.pem",
            host_path=_SERVER_CRT,
        ),
        BindMount(
            container_path="/etc/stunnel/stunnel.key",
            host_path=str(_cert_dir / "server.key"),
        ),
    ]
)

_STUNNEL_PYTHON_HTTP_TUNNEL_CTR = DerivedContainer(
    **_stunnel_kwargs,
    extra_environment_variables={
        "STUNNEL_DEBUG": "info",
        "STUNNEL_SERVICE_NAME": "python",
        "STUNNEL_ACCEPT": "0.0.0.0:8443",
        "STUNNEL_CONNECT": "0.0.0.0:8000",
    },
)

_PYTHON_WEB_SERVER = DerivedContainer(
    base="registry.suse.com/bci/python",
    containerfile="""
RUN echo "hello world" > index.html
ENTRYPOINT ["python3", "-m", "http.server"]
""",
)


_STUNNEL_POD = pytest.param(
    Pod(
        containers=[_PYTHON_WEB_SERVER, _STUNNEL_PYTHON_HTTP_TUNNEL_CTR],
        forwarded_ports=[PortForwarding(container_port=8443)],
    ),
)


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_exponential()
)
def get_request_to_stunnel_with_backoff(
    *, route: str = "", port: int
) -> requests.Response:
    """Perform a GET to `127.0.0.1:$port/$route` with an exponential backoff in
    case the response has a status other than 200 or times out.

    """
    resp = requests.get(
        f"https://127.0.0.1:{port}/{route}",
        # openssl older than 1.1.1l fails to validate a cert without CA
        verify=(
            _SERVER_CRT if ssl.OPENSSL_VERSION_NUMBER >= 0x101010CF else False
        ),
        timeout=5,
    )
    resp.raise_for_status()
    return resp


@pytest.mark.parametrize("pod", [_STUNNEL_POD], indirect=True)
def test_stunnel_http_proxy(pod: PodData):
    """Smoke test for stunnel to wrap a python http server in a TLS connection
    using the generated certificate. The python web server is running in its own
    container and stunnel in another one both in a single pod that only exposes
    the TLS endpoint.

    """

    assert (
        "hello world"
        in get_request_to_stunnel_with_backoff(
            port=pod.forwarded_ports[0].host_port
        ).text
    )


_CTR_PORT = 8000


def _create_http_forward_ctr(log_level: str = "info") -> DerivedContainer:
    return DerivedContainer(
        **_stunnel_kwargs,
        forwarded_ports=[PortForwarding(container_port=_CTR_PORT)],
        extra_environment_variables={
            "STUNNEL_DEBUG": log_level,
            "STUNNEL_SERVICE_NAME": "neverssl",
            "STUNNEL_ACCEPT": f"0.0.0.0:{_CTR_PORT}",
            "STUNNEL_CONNECT": "neverssl.com:80",
        },
    )


@pytest.mark.parametrize(
    "container", [_create_http_forward_ctr()], indirect=True
)
def test_http_tunnel_to_neverssl_com(container: ContainerData) -> None:
    """Simple smoke test of stunnel wrapping the HTTP connection to
    neverssl.com with TLS.

    """

    resp = get_request_to_stunnel_with_backoff(
        port=container.forwarded_ports[0].host_port
    )
    assert resp.status_code == 200
    assert "neverssl" in resp.text.lower()


@pytest.mark.parametrize(
    "container, log_level",
    [
        pytest.param(
            _create_http_forward_ctr("6"), 6, marks=STUNNEL_CONTAINER.marks
        ),
        pytest.param(
            _create_http_forward_ctr("1"), 1, marks=STUNNEL_CONTAINER.marks
        ),
    ],
    indirect=["container"],
)
def test_stunnel_logging(container: ContainerData, log_level: int) -> None:
    """Check that stunnel logging can be configured via the environment variable
    `STUNNEL_DEBUG`.

    """
    get_request_to_stunnel_with_backoff(
        port=container.forwarded_ports[0].host_port
    )

    _startup_log_levels = (5, 6)
    logs = container.read_container_logs()

    for search_log_level in range(7):
        if search_log_level <= log_level:
            if search_log_level in _startup_log_levels:
                assert f"LOG{search_log_level}" in logs
        else:
            assert f"LOG{search_log_level}" not in logs
