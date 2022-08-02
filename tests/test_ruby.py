import pytest

from bci_tester.data import RUBY_25_CONTAINER


CONTAINER_IMAGES = [RUBY_25_CONTAINER]


def test_ruby_version(auto_container):
    """Verify that the environment variable ``RUBY_VERSION`` and ``RUBY_MAJOR``
    match the version of Ruby in the container.

    """
    rb_ver = auto_container.connection.run_expect(
        [0], 'rpm -q --qf "%{VERSION}" ruby2.5'
    ).stdout.strip()
    assert (
        auto_container.connection.run_expect(
            [0], "echo $RUBY_VERSION"
        ).stdout.strip()
        == rb_ver
    )

    assert auto_container.connection.run_expect(
        [0], "echo $RUBY_MAJOR"
    ).stdout.strip() == ".".join(rb_ver.split(".")[:-1])


def test_lang_set(auto_container):
    """Assert that the environment variable ``LANG`` is set to ``C.UTF-8``."""
    assert (
        auto_container.connection.run_expect([0], "echo $LANG").stdout.strip()
        == "C.UTF-8"
    )


@pytest.mark.parametrize(
    "gem",
    [
        "ffi",
        pytest.param(
            "rails -v '<7.0'",
            marks=pytest.mark.xfail(reason="rails 6 is not installable"),
        ),
        "sqlite3",
        "rspec-expectations",
        "diff-lcs",
        "rspec-mocks",
        "rspec-support",
        "rspec",
        "multi_json",
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
    - rails < 7.0
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


@pytest.mark.xfail(reason="rails 6 is not installable")
def test_rails_hello_world(auto_container_per_test):
    auto_container_per_test.connection.run_expect(
        [0], "gem install rails -v '<7.0'"
    )
    auto_container_per_test.connection.run_expect(
        [0], "rails new /hello/ --minimal"
    )


@pytest.mark.xfail(reason="rails 6 is not installable")
def test_rails_template(auto_container_per_test):
    auto_container_per_test.connection.run_expect(
        [0], "gem install rails -v '<7.0'"
    )
    # auto_container_per_test.connection.run_expect([0], "zypper -n in npm nodejs")
    # auto_container_per_test.connection.run_expect([0], "npm -g install yarn")
    auto_container_per_test.connection.run_expect(
        [0], "rails new /hello/ --minimal"
    )

    add_template = auto_container_per_test.connection.run_expect(
        [0, 1],
        "cd /hello/ && rails app:template LOCATION='https://railsbytes.com/script/x9Qsqx'",
    )
    if (
        add_template.rc == 1
        and "TZInfo::DataSourceNotFound: tzinfo-data is not present. Please add gem 'tzinfo-data' to your Gemfile and run bundle install"
        in add_template.stderr.strip()
    ):
        pytest.xfail("timezone data are not in the container")

    curl_localhost = auto_container_per_test.connection.run_expect(
        [0],
        "cd /hello/ && (rails server > /dev/null &) && curl http://localhost:3000",
    )

    assert "Ruby on Rails" in curl_localhost.stdout.strip()
