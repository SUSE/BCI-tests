"""Tests for the PHP-cli, -apache and -fpm containers."""

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

import pytest
import requests
from pytest_container import DerivedContainer
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat
from pytest_container.container import PortForwarding
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import OS_VERSION
from bci_tester.data import PHP_8_APACHE
from bci_tester.data import PHP_8_CLI
from bci_tester.data import PHP_8_FPM

CONTAINER_IMAGES = [PHP_8_CLI, PHP_8_APACHE, PHP_8_FPM]

PHP_FLAVOR_T = Literal["apache", "fpm", "cli"]
CONTAINER_IMAGES_WITH_FLAVORS = [
    pytest.param(*t, marks=t[0].marks)
    for t in ((PHP_8_APACHE, "apache"), (PHP_8_FPM, "fpm"), (PHP_8_CLI, "cli"))
]
_PHP_MAJOR_VERSION = 8
_MEDIAWIKI_VERSION = "1.39.10"
_MEDIAWIKI_MAJOR_VERSION = ".".join(_MEDIAWIKI_VERSION.split(".")[:2])

MEDIAWIKI_APACHE_CONTAINER = DerivedContainer(
    base=PHP_8_APACHE,
    forwarded_ports=[PortForwarding(container_port=80)],
    image_format=ImageFormat.DOCKER,
    containerfile=f"""ENV MEDIAWIKI_VERSION={_MEDIAWIKI_VERSION}
ENV MEDIAWIKI_MAJOR_VERSION={_MEDIAWIKI_MAJOR_VERSION}"""
    + """
RUN set -e; zypper -n in $PHPIZE_DEPS oniguruma-devel libicu-devel gcc-c++ php8-sqlite php8-gd gzip && \
    for ext in mbstring intl fileinfo iconv calendar ctype dom; do \
        docker-php-ext-configure $ext; \
        docker-php-ext-install $ext; \
    done \
    && docker-php-source delete \
    && zypper -n rm oniguruma-devel libicu-devel gcc-c++ \
    && zypper -n clean && rm -rf /var/log/{zypp*,suseconnect*}

RUN set -euo pipefail; \
    zypper -n in tar; \
    curl -sfOL "https://releases.wikimedia.org/mediawiki/${MEDIAWIKI_MAJOR_VERSION}/mediawiki-${MEDIAWIKI_VERSION}.tar.gz"; \
    tar -xf "mediawiki-${MEDIAWIKI_VERSION}.tar.gz"; \
    rm "mediawiki-${MEDIAWIKI_VERSION}.tar.gz"; \
    pushd "mediawiki-${MEDIAWIKI_VERSION}/"; mv * ..; popd; rmdir "mediawiki-${MEDIAWIKI_VERSION}"; \
    php maintenance/install.php --dbname mediawiki.db --dbtype sqlite --pass insecureAndAtLeast10CharsLong --scriptpath="" --server="http://localhost" test-wiki geeko; \
    chown --recursive wwwrun data; \
    zypper -n clean; rm -rf /var/log/{zypp*,suseconnect*}

HEALTHCHECK --interval=10s --timeout=1s --retries=10 CMD curl -sf http://localhost
EXPOSE 80
""",
)


MEDIAWIKI_FPM_CONTAINER = DerivedContainer(
    base=PHP_8_FPM,
    containerfile=f"""ENV MEDIAWIKI_VERSION={_MEDIAWIKI_VERSION}
ENV MEDIAWIKI_MAJOR_VERSION={_MEDIAWIKI_MAJOR_VERSION}"""
    + r"""
RUN set -eux; \
    zypper -n ref; \
    zypper -n up; \
    zypper -n in $PHPIZE_DEPS php8-pecl oniguruma-devel git \
                librsvg \
                ImageMagick \
                python3; # Required for SyntaxHighlighting

# Install the PHP extensions we need
RUN set -eux; \
    zypper -n in libicu-devel php8-mysql php8-sqlite; \
        docker-php-ext-install \
                calendar \
                intl \
                mbstring \
                opcache \
                iconv \
                ctype \
                fileinfo \
                dom ; \
        pecl install APCu-5.1.21; \
        docker-php-ext-enable apcu; \
        rm -r /tmp/pear


# set recommended PHP.ini settings
# see https://secure.php.net/manual/en/opcache.installation.php
RUN { \
                echo 'opcache.memory_consumption=128'; \
                echo 'opcache.interned_strings_buffer=8'; \
                echo 'opcache.max_accelerated_files=4000'; \
                echo 'opcache.revalidate_freq=60'; \
        } > /etc/php8/conf.d/opcache-recommended.ini

# SQLite Directory Setup
RUN set -eux; \
        mkdir -p data; \
        chown -R wwwrun data

# pre-fetched keys from https://www.mediawiki.org/keys/keys.txt
COPY tests/files/mariadb-keys.asc /tmp/mariadb-keys.asc

# MediaWiki setup
RUN set -eux; \
    zypper -n in dirmngr gzip; \
        curl -sfSL "https://releases.wikimedia.org/mediawiki/${MEDIAWIKI_MAJOR_VERSION}/mediawiki-${MEDIAWIKI_VERSION}.tar.gz" -o mediawiki.tar.gz; \
        curl -sfSL "https://releases.wikimedia.org/mediawiki/${MEDIAWIKI_MAJOR_VERSION}/mediawiki-${MEDIAWIKI_VERSION}.tar.gz.sig" -o mediawiki.tar.gz.sig; \
        export GNUPGHOME="$(mktemp -d)"; \
        # import gpg keys from https://www.mediawiki.org/keys/keys.txt
        gpg --import /tmp/mariadb-keys.asc; \
        gpg --batch --verify mediawiki.tar.gz.sig mediawiki.tar.gz; \
        tar -x --strip-components=1 -f mediawiki.tar.gz; \
        gpgconf --kill all; \
        rm -r "$GNUPGHOME" mediawiki.tar.gz.sig mediawiki.tar.gz; \
        chown -R wwwrun extensions skins cache images data; \
        php maintenance/install.php --dbname mediawiki.db --dbtype sqlite --pass insecureAndAtLeast10CharsLong --scriptpath="" --server="http://localhost" test-wiki geeko && \
        chown --recursive wwwrun data; \
        zypper -n rm dirmngr gzip;

CMD ["php-fpm"]
""",
)

NGINX_FPM_PROXY = DerivedContainer(
    base="registry.opensuse.org/opensuse/nginx",
    containerfile="""COPY tests/files/nginx.conf /etc/nginx/
COPY tests/files/fastcgi_params /etc/nginx/
""",
)

MEDIAWIKI_FPM_POD = Pod(
    containers=[MEDIAWIKI_FPM_CONTAINER, NGINX_FPM_PROXY],
    forwarded_ports=[PortForwarding(container_port=80)],
)


def test_install_phpize_deps(auto_container_per_test: ContainerData):
    """Check that we can install whatever is in the environment variable
    ``PHPIZE_DEPS`` and that afterwards :command:`phpize` works.

    """
    auto_container_per_test.connection.run_expect(
        [0],
        "zypper -n in $PHPIZE_DEPS",
    )
    auto_container_per_test.connection.run_expect([0], "touch config.m4")
    auto_container_per_test.connection.run_expect([0], "phpize")


@pytest.mark.parametrize("extension", ["pcntl", "gd"])
def test_install_php_extension_via_script(
    auto_container_per_test: ContainerData, extension: str
):
    """Verify that :command:`docker-php-ext-configuer $ex &&
    docker-php-ext-install` works for the ``pcntl`` and ``gd`` extensions and
    that both are present in the output of :command:`php -m` after running the
    former command.

    """
    auto_container_per_test.connection.run_expect(
        [0], f"docker-php-ext-configure {extension}"
    )
    auto_container_per_test.connection.run_expect(
        [0], f"docker-php-ext-install {extension}"
    )

    assert extension in auto_container_per_test.connection.check_output(
        "php -m"
    )


def test_install_multiple_extensions_via_script(
    auto_container_per_test: ContainerData,
) -> None:
    """Try to install multiple extensions at the same time via
    :command:`docker-php-ext-install $ext1 $ext2` and check that they have
    actually been installed via :command:`zypper`.

    """
    extensions = [
        "calendar",
        "intl",
        "mbstring",
        "opcache",
        "iconv",
        "ctype",
        "fileinfo",
        "dom",
    ]

    auto_container_per_test.connection.run_expect(
        [0], f"docker-php-ext-install {' '.join(extensions)}"
    )
    for ext in extensions:
        assert auto_container_per_test.connection.package(
            f"php{_PHP_MAJOR_VERSION}-{ext}"
        ).is_installed


@pytest.mark.parametrize("extension_name", ["gd"])
def test_zypper_install_php_extensions(
    auto_container_per_test: ContainerData, extension_name: str
):
    """Test that the ``gd`` extension is not registered with php before
    installing ``php$ver-gd``, and that it is after installing the package
    ``php$ver-gd``.

    """
    assert (
        extension_name
        not in auto_container_per_test.connection.check_output("php -m")
    )
    auto_container_per_test.connection.run_expect(
        [0], f"zypper -n in php{_PHP_MAJOR_VERSION}-{extension_name}"
    )
    assert extension_name in auto_container_per_test.connection.check_output(
        "php -m"
    )


@pytest.mark.parametrize(
    "container_per_test,flavor",
    CONTAINER_IMAGES_WITH_FLAVORS,
    indirect=["container_per_test"],
)
def test_environment_variables(
    container_per_test: ContainerData, flavor: PHP_FLAVOR_T
):
    """Sanity check of the environment variables:
    - ``PHP_VERSION``
    - ``COMPOSER_VERSION``
    - ``PHP_INI_DIR``

    and specific to php-apache variant:
    - ``APACHE_CONFDIR``
    - ``APACHE_ENVVARS``
    """

    def get_env_var(env_var: str) -> str:
        return container_per_test.connection.check_output(f"echo ${env_var}")

    php_pkg_version = container_per_test.connection.package(
        f"php{_PHP_MAJOR_VERSION}"
    ).version
    assert php_pkg_version == get_env_var("PHP_VERSION")

    assert container_per_test.connection.package(
        "php-composer2"
    ).version == get_env_var("COMPOSER_VERSION")

    php_ini_dir_path = get_env_var("PHP_INI_DIR")
    php_ini_dir = container_per_test.connection.file(php_ini_dir_path)
    assert php_ini_dir.exists and php_ini_dir.is_directory

    if flavor == "apache":
        apache_confdir = get_env_var("APACHE_CONFDIR")
        assert container_per_test.connection.file(apache_confdir).is_directory
        assert container_per_test.connection.file(
            f"{apache_confdir}/httpd.conf"
        ).is_file

        if OS_VERSION in ("15.3", "15.4", "15.5"):
            apache_envvars = get_env_var("APACHE_ENVVARS")
            assert container_per_test.connection.file(apache_envvars).is_file
            assert container_per_test.connection.run_expect(
                [0], f"source {apache_envvars}"
            )


@pytest.mark.parametrize("container_image", [PHP_8_CLI])
def test_cli_entry_point(
    container_image: DerivedContainer,
    container_runtime: OciRuntimeBase,
    host,
    pytestconfig: pytest.Config,
) -> None:
    """Smoke test of the entrypoint of the php-cli variant: run the container
    and verify that the arguments ``-r 'print_r(get_defined_constants());'`` are
    forwarded to :command:`php`.

    """
    container_image.prepare_container(container_runtime, pytestconfig.rootpath)

    assert "PHP_BINARY" in host.check_output(
        f"{container_runtime.runner_binary} run --rm "
        f"{container_image.url or container_image.container_id} -r 'print_r(get_defined_constants());'",
    )


@pytest.mark.parametrize(
    "container_per_test",
    [MEDIAWIKI_APACHE_CONTAINER],
    indirect=["container_per_test"],
)
def test_mediawiki_php_apache(container_per_test: ContainerData) -> None:
    """Application test of the php-apache variant.

    This test builds mediawiki deployed via mod_php. The test itself just checks
    if the container is reachable using requests.

    """

    resp = requests.get(
        f"http://localhost:{container_per_test.forwarded_ports[0].host_port}",
        timeout=30,
        # we will get redirected to https://localhost, which will not resolve, so forbid that
        allow_redirects=False,
    )
    resp.raise_for_status()


@pytest.mark.parametrize(
    "pod_per_test", [MEDIAWIKI_FPM_POD], indirect=["pod_per_test"]
)
def test_mediawiki_fpm_build(pod_per_test: PodData) -> None:
    """Application test of the php-fpm variant.

    This test builds mediawiki deployed via fpm with a nginx proxy in front of
    it, both deployed via two containers in a podman pod.  The test itself just
    checks if the pod is reachable using requests.

    """
    resp = requests.get(
        f"http://localhost:{pod_per_test.forwarded_ports[0].host_port}",
        timeout=30,
    )
    resp.raise_for_status()
