"""This module contains the tests for the postfix container, the image with postfix, sendmail and mailq pre-installed."""

import pytest
from pytest_container import container_and_marks_from_pytest_param
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat

from bci_tester.data import POSTFIX_CONTAINERS

CONTAINER_IMAGES = POSTFIX_CONTAINERS

POSTFIX_WITH_LOGGING_ENABLED = []
POSTFIX_WITH_MAILHOG = []
POSTFIX_WITH_VIRTUAL_MBOX_ENABLED = []


CONTAINERFILE_POSTFIX_WITH_LOGGING_ENABLED = """
RUN postconf maillog_file=/var/log/postfix.log 
RUN postconf maillog_file_permissions=0644
HEALTHCHECK --interval=5s --timeout=10s --start-period=30s --retries=3 \
        CMD postfix status
"""


CONTAINERFILE_POSTFIX_WITH_MAILHOG = """
RUN set -euo pipefail; \
    curl -L -o /usr/local/bin/mailhog https://github.com/mailhog/MailHog/releases/download/v1.0.1/MailHog_linux_amd64; \
    chmod +x /usr/local/bin/mailhog
EXPOSE 1025 8025
HEALTHCHECK --interval=5s --timeout=10s --start-period=30s --retries=3 \
        CMD postfix status
"""

for postfix_ctr in POSTFIX_CONTAINERS:
    ctr, marks = container_and_marks_from_pytest_param(postfix_ctr)
    POSTFIX_WITH_LOGGING_ENABLED.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                forwarded_ports=ctr.forwarded_ports,
                containerfile=CONTAINERFILE_POSTFIX_WITH_LOGGING_ENABLED,
                extra_environment_variables=ctr.extra_environment_variables,
                image_format=ImageFormat.DOCKER,
            ),
            marks=marks,
        )
    )


for postfix_ctr in POSTFIX_WITH_LOGGING_ENABLED:
    ctr, marks = container_and_marks_from_pytest_param(postfix_ctr)
    POSTFIX_WITH_MAILHOG.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                forwarded_ports=ctr.forwarded_ports,
                containerfile=CONTAINERFILE_POSTFIX_WITH_MAILHOG,
                extra_environment_variables={
                    "SERVER_HOSTNAME": "localhost",
                    "SMTP_RELAYHOST": "localhost",  # pointing to mailhog running locally
                    "SMTP_PORT": "1025",
                },
                image_format=ImageFormat.DOCKER,
            ),
            marks=marks,
        )
    )


for postfix_ctr in POSTFIX_WITH_MAILHOG:
    ctr, marks = container_and_marks_from_pytest_param(postfix_ctr)
    POSTFIX_WITH_VIRTUAL_MBOX_ENABLED.append(
        pytest.param(
            DerivedContainer(
                base=ctr,
                forwarded_ports=ctr.forwarded_ports,
                containerfile=CONTAINERFILE_POSTFIX_WITH_MAILHOG,
                extra_environment_variables={
                    "SERVER_HOSTNAME": "localhost",
                    "SMTP_RELAYHOST": "localhost",  # pointing to mailhog running locally
                    "SMTP_PORT": "1025",
                    "VIRTUAL_MBOX": "1",
                    "VMAIL_UID": "5000",
                    "VIRTUAL_DOMAINS": "example.com example1.com",
                    "VIRTUAL_USERS": "user1@example.com user2@example.com user@example1.com",
                },
                image_format=ImageFormat.DOCKER,
            ),
            marks=marks,
        )
    )


def test_postfix_status(auto_container):
    # verify PID 1 process is ENTRYPOINT - `/bin/bash /entrypoint/entrypoint.sh postfix start`
    assert (
        "/bin/bash /entrypoint/entrypoint.sh postfix start"
        in auto_container.connection.check_output(
            "ps -eo pid,cmd | grep '^ *1 ' | sed 's/^ *1 //'"
        )
    )

    # check if Postfix service is running inside the container
    assert (
        "the Postfix mail system is running"
        in auto_container.connection.check_output("postfix status 2>&1")
    )


@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_LOGGING_ENABLED, indirect=True
)
def test_postfix_send_email_delivered(
    container_per_test: ContainerData,
) -> None:
    # test sending an email successfully to localhost, using Postfix container

    assert container_per_test.connection.file("/var/log/postfix.log").exists

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -v root@localhost'
    assert container_per_test.connection.run_expect([0], sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "mailq"
    )

    for output in [
        "from=<root@localhost>",
        "dsn=2.0.0",
        "status=sent (delivered to mailbox)",
        "relay=local",
    ]:
        assert output in container_per_test.connection.check_output(
            "cat /var/log/postfix.log"
        )


@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_LOGGING_ENABLED, indirect=True
)
def test_postfix_send_email_failed(
    container_per_test: ContainerData,
) -> None:
    # send a test email using the Postfix container, which fails

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    assert container_per_test.connection.run_expect([0], sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "mailq"
    )

    for output in [
        "to=<user1@example.com>",
        "dsn=5.1.0",
        "status=bounced (Domain example.com does not accept mail (nullMX))",
        "relay=none",
    ]:
        assert output in container_per_test.connection.check_output(
            "cat /var/log/postfix.log"
        )


@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_MAILHOG, indirect=True
)
def test_postfix_relay_email_to_mailhog(
    container_per_test: ContainerData,
) -> None:
    # test relayin an email successfully to SMTP_RELAYHOST, using Postfix container

    assert container_per_test.connection.run_expect(
        [0], "nohup /usr/local/bin/mailhog > /dev/null 2>&1 &"
    )

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    assert container_per_test.connection.run_expect([0], sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "mailq"
    )

    for output in [
        "from=<user1@example.com>",
        "to=<user2@example.com>",
        "relay=localhost[127.0.0.1]:1025",
        "dsn=2.0.0",
        "status=sent (250 Ok: queued as ",
        "=@mailhog.example)",
    ]:
        assert output in container_per_test.connection.check_output(
            "cat /var/log/postfix.log"
        )


@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_VIRTUAL_MBOX_ENABLED, indirect=True
)
def test_postfix_send_email_delivered_to_virtual_mbox(
    container_per_test: ContainerData,
) -> None:
    # test sending an email successfully to virtual mailbox, using Postfix container 

    assert container_per_test.connection.run_expect(
        [0], "chown -R vmail:vmail /var/spool/vmail/"
    )
    assert container_per_test.connection.run_expect(
        [0], "nohup /usr/local/bin/mailhog > /dev/null 2>&1 &"
    )

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    assert container_per_test.connection.run_expect([0], sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "mailq"
    )

    for output in [
        "from=<user1@example.com>",
        "to=<user2@example.com>",
        "relay=virtual",
        "dsn=2.0.0",
        "status=sent (delivered to maildir)",
    ]:
        assert output in container_per_test.connection.check_output(
            "cat /var/log/postfix.log"
        )

    assert container_per_test.connection.file(
        "/var/spool/vmail/example.com/user2"
    ).exists
