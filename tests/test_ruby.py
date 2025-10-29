"""Basic tests for the Ruby base container images."""

import pytest

from bci_tester.data import OS_VERSION
from bci_tester.data import RUBY_CONTAINERS

CONTAINER_IMAGES = RUBY_CONTAINERS


def test_ruby_version(auto_container):
    """Verify that the environment variable ``RUBY_VERSION`` and ``RUBY_MAJOR``
    match the version of Ruby in the container.

    """
    rb_ver = auto_container.connection.check_output(
        "ruby -e 'puts RUBY_VERSION'"
    )
    assert (
        auto_container.connection.check_output("echo $RUBY_VERSION") == rb_ver
    )

    assert auto_container.connection.check_output(
        "echo $RUBY_MAJOR"
    ) == ".".join(rb_ver.split(".")[:-1])


def test_lang_set(auto_container):
    """Assert that the environment variable ``LANG`` is set to ``C.UTF-8``."""
    assert auto_container.connection.check_output("echo $LANG") == "C.UTF-8"


@pytest.mark.parametrize(
    "gem",
    [
        (  # bsc1225821
            ("--platform ruby " if OS_VERSION != "tumbleweed" else "") + "ffi"
        ),
        (
            # bsc#1203692
            "sqlite3 -v 1.4.0"
            if OS_VERSION in ("15.5", "15.6", "15.7")
            else "sqlite3"
        ),
        "rspec-expectations",
        "diff-lcs",
        "rspec-mocks",
        "rspec-support",
        "rspec",
        (
            "multi_json -v 1.15.0"
            if OS_VERSION in ("15.5", "15.6", "15.7")
            else "multi_json"
        ),
        "rack",
        "rake",
        "i18n",
    ],
)
def test_install_gems(auto_container_per_test, gem):
    """Check that we can :command:`gem install` a few commonly used and/or
    popular gems (this is a selection from
    `<https://rubygems.org/search?query=downloads%3A+%3E400000>`_):

    - ffi
    - sqlite3
    - rspec-expectations
    - diff-lcs
    - rspec-mocks
    - rspec-support
    - rspec
    - multi_json
    - rack
    - rake
    - i18n
    """
    auto_container_per_test.connection.run_expect([0], f"gem install {gem}")


@pytest.mark.skipif(
    OS_VERSION != "tumbleweed", reason="no yarn (needed by rails) in SLE"
)
def test_rails_hello_world(auto_container_per_test):
    """Check that we can install Rails and create a new minimal Rails application."""
    auto_container_per_test.connection.check_output("gem install 'rails'")

    # Rails asset pipeline needs Node.js and yarn
    auto_container_per_test.connection.check_output(
        "zypper -n in nodejs-default yarn libyaml-devel"
    )
    auto_container_per_test.connection.check_output(
        "rails new /hello/ --minimal"
    )


def test_rails_template(auto_container_per_test):
    """Check that we can install Rails and create a new Rails application from a template."""

    if auto_container_per_test.connection.check_output(
        "echo $RUBY_VERSION"
    ).startswith("2.5"):
        pytest.xfail("Rails 8 needs Ruby >= 3.0")

    # Rails asset pipeline needs Node.js and yarn. apps:template needs libxslt
    auto_container_per_test.connection.check_output(
        "zypper -n in nodejs-default libyaml-devel libxslt1"
    )

    auto_container_per_test.connection.check_output(
        "gem install 'rails:~> 8.0'"
    )

    # auto_container_per_test.connection.run_expect([0], "zypper -n in npm nodejs")
    # auto_container_per_test.connection.run_expect([0], "npm -g install yarn")
    auto_container_per_test.connection.check_output(
        "rails new /hello/ --minimal"
    )

    # https://railsbytes.com/public/templates/x7msKX
    add_template = auto_container_per_test.connection.run_expect(
        [0, 1],
        "cd /hello/ && rails app:template LOCATION='https://railsbytes.com/script/x7msKX'",
    )
    if (
        add_template.rc == 1
        and "TZInfo::DataSourceNotFound: tzinfo-data is not present. Please add gem 'tzinfo-data' to your Gemfile and run bundle install"
        in add_template.stderr.strip()
    ):
        pytest.xfail("timezone data are not in the container")

    assert "Ruby on Rails" in auto_container_per_test.connection.check_output(
        "cd /hello/ && (rails server > /dev/null &) && curl -sf --retry 5 --retry-connrefused  http://localhost:3000",
    )
