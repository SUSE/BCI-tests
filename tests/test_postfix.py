"""This module contains the tests for the postfix container, the image with postfix, sendmail and mailq pre-installed."""

import pytest
from pytest_container import DerivedContainer
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat

from bci_tester.data import OS_VERSION
from bci_tester.data import POSTFIX_CONTAINERS

CONTAINER_IMAGES = POSTFIX_CONTAINERS

POSTFIX_WITH_MAILHOG = []
POSTFIX_WITH_VIRTUAL_MBOX_ENABLED = []
POSTFIX_WITH_LDAP_ENABLED = []


CONTAINERFILE_POSTFIX_WITH_MAILHOG = """
ENV MAILHOG_VERSION="v1.0.1"
RUN set -euo pipefail; \
    curl -L -o /usr/local/bin/mailhog https://github.com/mailhog/MailHog/releases/download/${MAILHOG_VERSION}/MailHog_linux_amd64; \
    chmod +x /usr/local/bin/mailhog
EXPOSE 1025 8025
HEALTHCHECK --interval=5s --timeout=10s --start-period=30s --retries=3 \
        CMD postfix status
"""


CONTAINERFILE_POSTFIX_WITH_LDAP_ENABLED = """
# TODO: move postfix & openldap container files to bci-dockerfile-generator
RUN set -euo pipefail; \
    curl -Lsf -o - https://github.com/thkukuk/containers-mailserver/archive/refs/heads/master.tar.gz | tar  --no-same-permissions --no-same-owner -xzf - && \
    cd containers-mailserver-master/openldap && \
    cp -r ldif /entrypoint/ && \
    cp slapd.init.ldif /entrypoint/ && \
    cp entrypoint.sh /entrypoint/openldap-entrypoint.sh

RUN FILE="/entrypoint/openldap-entrypoint.sh" && \
    for cmd in \
        's|-h "$LDAP_URL $LDAPS_URL $LDAPI_URL" ${SLAPD_SLP_REG}|-h "$LDAP_URL $LDAPS_URL $LDAPI_URL" ${SLAPD_SLP_REG} > /var/log/slapd.log 2>\\&1 \\&|' \
        's|exec /usr/sbin/slapd -d "${SLAPD_LOG_LEVEL}" -u ldap -g ldap|exec nohup /usr/sbin/slapd -d "${SLAPD_LOG_LEVEL}" -u ldap -g ldap|' \
        's|ldapadd -c -Y EXTERNAL -Q -H ldapi:/// -f /etc/openldap/schema/ppolicy.ldif||' \
    ; do \
        sed -i "$cmd" "$FILE"; \
    done

RUN echo 'dn: uid=user1,ou=mail,dc=example,dc=com' > /entrypoint/ldif/examples/example-user.ldif && \
    echo 'cn: user1' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'gidnumber: 20001' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'homedirectory: /home/mail/user1' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'mailacceptinggeneralid: user1@example.com' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'maildrop: user1@mail.example.com' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: account' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: posixAccount' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: postfixUser' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: top' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'uid: user1' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'uidnumber: 20001' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'userpassword: user1' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo '' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'dn: uid=user2,ou=mail,dc=example,dc=com' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'cn: user2' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'gidnumber: 20002' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'homedirectory: /home/mail/user2' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'mailacceptinggeneralid: user2@example.com' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'maildrop: user2@mail.example.com' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: account' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: posixAccount' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: postfixUser' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'objectclass: top' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'uid: user2' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'uidnumber: 20002' >> /entrypoint/ldif/examples/example-user.ldif && \
    echo 'userpassword: user2' >> /entrypoint/ldif/examples/example-user.ldif

HEALTHCHECK --interval=5s --timeout=10s --start-period=30s --retries=3 \
        CMD postfix status
"""


for ctr in POSTFIX_CONTAINERS:
    POSTFIX_WITH_MAILHOG.append(
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
        )
    )


for ctr in POSTFIX_WITH_MAILHOG:
    POSTFIX_WITH_VIRTUAL_MBOX_ENABLED.append(
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
        )
    )


for ctr in POSTFIX_WITH_VIRTUAL_MBOX_ENABLED:
    POSTFIX_WITH_LDAP_ENABLED.append(
        DerivedContainer(
            base=ctr,
            forwarded_ports=ctr.forwarded_ports,
            containerfile=CONTAINERFILE_POSTFIX_WITH_LDAP_ENABLED,
            extra_environment_variables={
                "SERVER_HOSTNAME": "localhost",
                "SMTP_RELAYHOST": "localhost",  # pointing to mailhog running locally
                "SMTP_PORT": "1025",
                "VIRTUAL_MBOX": "1",
                "VMAIL_UID": "5000",
                "USE_LDAP": "1",
                "LDAP_BASE_DN": "dc=example,dc=com",
                "LDAP_BIND_DN": "cn=admin,dc=example,dc=com",
                "LDAP_BIND_PASSWORD": "admin",
                "LDAP_USE_TLS": "0",
                "LDAP_TLS": "0",
                "LDAP_DOMAIN": "example.com",
                "LDAP_ADMIN_PASSWORD": "admin",
                "LDAP_CONFIG_PASSWORD": "config",
                "SETUP_FOR_MAILSERVER": "1",
                "MAIL_ACCOUNT_READER_PASSWORD": "admin",
                "LDAP_SERVER_URL": "ldap://localhost",
            },
            image_format=ImageFormat.DOCKER,
        )
    )


def test_postfix_status(auto_container: ContainerData):
    """check if Postfix service is running inside the container"""

    # verify PID 1 process is ENTRYPOINT:
    # /bin/bash /entrypoint/entrypoint.sh postfix start

    # we don't have ps in the container, so read /proc/1/cmdline instead, it
    # contains the binary and its arguments separated by \x00
    cmdline: str = auto_container.connection.file(
        "/proc/1/cmdline"
    ).content_string
    assert "/usr/lib/postfix/bin//master -i" in cmdline.replace("\x00", " ")

    assert (
        "the Postfix mail system is running"
        in auto_container.connection.check_output("postfix status 2>&1")
    )


def test_postfix_send_email_delivered(auto_container_per_test):
    """test sending an email successfully to localhost, using Postfix container"""

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -v root@localhost'
    auto_container_per_test.connection.check_output(sendmail_cmd)

    assert (
        "Mail queue is empty"
        in auto_container_per_test.connection.check_output("sleep 10; mailq")
    )

    log = auto_container_per_test.read_container_logs()
    for output in [
        "from=<root@localhost>",
        "dsn=2.0.0",
        "status=sent (delivered to mailbox)",
        "relay=local",
    ]:
        assert output in log


def test_postfix_send_email_failed(auto_container_per_test):
    """send a test email using the Postfix container, which fails"""

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    auto_container_per_test.connection.check_output(sendmail_cmd)

    assert (
        "Mail queue is empty"
        in auto_container_per_test.connection.check_output("sleep 10; mailq")
    )

    log = auto_container_per_test.read_container_logs()
    for output in [
        "to=<user1@example.com>",
        "dsn=5.1.0",
        "status=bounced (Domain example.com does not accept mail (nullMX))",
        "relay=none",
    ]:
        assert output in log


@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_MAILHOG, indirect=True
)
def test_postfix_relay_email_to_mailhog(
    container_per_test: ContainerData,
) -> None:
    """test relaying an email successfully to SMTP_RELAYHOST, using Postfix container"""

    container_per_test.connection.check_output(
        "nohup /usr/local/bin/mailhog > /dev/null 2>&1 &"
    )

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    container_per_test.connection.check_output(sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "sleep 10; mailq"
    )

    log = container_per_test.read_container_logs()
    for output in [
        "from=<user1@example.com>",
        "to=<user2@example.com>",
        "relay=localhost[127.0.0.1]:1025",
        "dsn=2.0.0",
        "status=sent (250 Ok: queued as ",
        "=@mailhog.example)",
    ]:
        assert output in log


@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_VIRTUAL_MBOX_ENABLED, indirect=True
)
def test_postfix_send_email_delivered_to_virtual_mbox(
    container_per_test: ContainerData,
) -> None:
    """test sending an email successfully to virtual mailbox, using Postfix container"""

    container_per_test.connection.check_output(
        "chown -R vmail:vmail /var/spool/vmail/"
    )
    container_per_test.connection.check_output(
        "nohup /usr/local/bin/mailhog > /dev/null 2>&1 &"
    )

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    container_per_test.connection.check_output(sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "sleep 10; mailq"
    )

    log = container_per_test.read_container_logs()
    for output in [
        "from=<user1@example.com>",
        "to=<user2@example.com>",
        "relay=virtual",
        "dsn=2.0.0",
        "status=sent (delivered to maildir)",
    ]:
        assert output in log

    assert container_per_test.connection.file(
        "/var/spool/vmail/example.com/user2"
    ).exists


@pytest.mark.skipif(
    OS_VERSION != "tumbleweed",
    reason="openldap2 package only available on Tumbleweed (in the main system)",
)
@pytest.mark.parametrize(
    "container_per_test", POSTFIX_WITH_LDAP_ENABLED, indirect=True
)
def test_postfix_with_ldap_and_email_delivered(
    container_per_test: ContainerData,
) -> None:
    """test relaying an email successfully with ldap lookup, using Postfix container"""

    container_per_test.connection.check_output(
        "nohup /usr/local/bin/mailhog > /dev/null 2>&1 &"
    )

    container_per_test.connection.check_output(
        "/entrypoint/openldap-entrypoint.sh /usr/sbin/slapd"
    )
    assert container_per_test.connection.socket(
        "tcp://0.0.0.0:389"
    ).is_listening

    ldapsearch_query_stdout = container_per_test.connection.check_output(
        'ldapsearch -x -D "cn=admin,dc=example,dc=com" -w admin -b "dc=example,dc=com" "(cn=mailAccountReader)" dn'
    )
    for resp in [
        "dn: cn=mailAccountReader,ou=Manager,dc=example,dc=com",
        "result: 0 Success",
    ]:
        assert resp in ldapsearch_query_stdout

    container_per_test.connection.check_output(
        'ldapadd -x -D "cn=admin,dc=example,dc=com" -w "admin" -f /entrypoint/ldif/examples/example-user.ldif',
    )

    sendmail_cmd = 'echo "Subject: Test Email\n\nThis is a test email body." | sendmail -f user1@example.com user2@example.com'
    container_per_test.connection.check_output(sendmail_cmd)

    assert "Mail queue is empty" in container_per_test.connection.check_output(
        "sleep 10; mailq"
    )

    log = container_per_test.read_container_logs()
    for output in [
        "from=<user1@example.com>",
        "to=<user2@mail.example.com>, orig_to=<user2@example.com>",
        "relay=localhost[127.0.0.1]:1025",
        "dsn=2.0.0",
        "status=sent (250 Ok: queued as",
        "=@mailhog.example)",
    ]:
        assert output in log
