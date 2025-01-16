"""This module contains the tests for the git container, the image with git pre-installed."""

import pytest
from pytest_container.container import DerivedContainer
from pytest_container.container import ImageFormat
from pytest_container.pod import Pod
from pytest_container.pod import PodData
from pytest_container.runtime import LOCALHOST

from bci_tester.data import GIT_CONTAINER

CONTAINER_IMAGES = (GIT_CONTAINER,)

_PRIV_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACDJMR7NW+gNZGborupz8XoZEjuKRuKjLzVPAwfPcjrTzQAAAIi/QgI2v0IC
NgAAAAtzc2gtZWQyNTUxOQAAACDJMR7NW+gNZGborupz8XoZEjuKRuKjLzVPAwfPcjrTzQ
AAAEBACrN2+98i3BPX40CQxih8gRePIokGrmrobXVnNja+XckxHs1b6A1kZuiu6nPxehkS
O4pG4qMvNU8DB89yOtPNAAAAA0JDSQEC
-----END OPENSSH PRIVATE KEY-----"""

_PUB_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMkxHs1b6A1kZuiu6nPxehkSO4pG4qMvNU8DB89yOtPN BCI"

_SSH_PORT = 22022

_GIT_SERVER_CONTAINERFILE = (
    rf"""
RUN zypper -n in git-core openssh-server openssh-clients
RUN ssh-keygen -A
RUN useradd -U -m -p "*" git

RUN mkdir /home/git/.ssh && touch /home/git/.ssh/authorized_keys
RUN chmod 700 /home/git/.ssh && chmod 600 /home/git/.ssh/authorized_keys
RUN chown -R git:git /home/git/.ssh
RUN echo "{_PUB_KEY}" >> /home/git/.ssh/authorized_keys

RUN mkdir -p /srv/git/project.git
RUN chown git:git /srv/git/project.git
RUN git -C /srv/git/project.git init --bare

RUN echo -e '\
Port {_SSH_PORT}\n\
ListenAddress 0.0.0.0\n\
AuthorizedKeysFile      .ssh/authorized_keys\n\
ChallengeResponseAuthentication no\n\
PasswordAuthentication no\n\
PermitRootLogin no\n\
PubkeyAuthentication yes\n\
AllowUsers git\n\
UsePAM no\n\
AllowTcpForwarding no\n\
X11Forwarding no\n\
Subsystem       sftp    /usr/lib/ssh/sftp-server\n\
' > /etc/ssh/sshd_config

EXPOSE {_SSH_PORT}

CMD ["/usr/sbin/sshd", "-De"]

HEALTHCHECK --interval=5s --timeout=5s --retries=5"""
    + (" --start-period=1m" if LOCALHOST.system_info.arch == "ppc64le" else "")
    + f""" CMD ["/usr/bin/ssh-keyscan", "-vvv", "-H", "-p", "{_SSH_PORT}", "127.0.0.1"]
"""
)


def test_git_version(auto_container):
    """Smoke test that the output of :command:`git --version` looks sane."""
    assert "git version 2." in auto_container.connection.check_output(
        "git --version"
    )


def test_git_clone_https(auto_container_per_test):
    """Test that we can clone a repository over HTTPS successfully."""
    auto_container_per_test.connection.check_output(
        "git clone https://github.com/github/gemoji.git /gemoji"
    )
    assert auto_container_per_test.connection.file("/gemoji/.git/HEAD").exists
    assert auto_container_per_test.connection.file("/gemoji/Gemfile").exists
    assert auto_container_per_test.connection.file(
        "/gemoji/db/emoji.json"
    ).exists
    out = auto_container_per_test.connection.check_output(
        "git -C /gemoji status"
    )
    assert "Your branch is up to date" in out
    assert "nothing to commit, working tree clean" in out


GIT_SERVER_CONTAINER = DerivedContainer(
    base="registry.suse.com/bci/bci-base:latest",
    containerfile=_GIT_SERVER_CONTAINERFILE,
    image_format=ImageFormat.DOCKER,
    extra_launch_args=["--cap-add", "AUDIT_WRITE"],
)


GIT_POD = Pod(
    containers=[GIT_SERVER_CONTAINER, GIT_CONTAINER],
)


@pytest.mark.parametrize("pod_per_test", [GIT_POD], indirect=True)
def test_git_clone_ssh(pod_per_test: PodData) -> None:
    """Test that we can clone a repository over SSH successfully."""
    cli = pod_per_test.container_data[1].connection
    srv = pod_per_test.container_data[0]
    host = srv.inspect.network.ip_address or "127.0.0.1"

    cli.check_output("mkdir /root/.ssh")
    cli.check_output(f'echo -e "{_PRIV_KEY}" > /root/.ssh/id_ed25519')
    cli.check_output("chmod 0600 /root/.ssh/id_ed25519")
    cli.check_output("eval `ssh-agent -s` && ssh-add /root/.ssh/id_ed25519")
    cli.check_output(
        f"ssh-keyscan -vvv -p {_SSH_PORT} {host} >> /root/.ssh/known_hosts"
    )

    cli.check_output(
        f"git clone ssh://git@{host}:{_SSH_PORT}/srv/git/project.git /project"
    )
    assert cli.file("/project/.git/HEAD").exists
    out = cli.check_output("git -C /project status")

    assert "No commits yet" in out
    assert "nothing to commit" in out


def test_git_init(auto_container_per_test):
    """Test that we can init a repository successfully."""
    auto_container_per_test.connection.check_output("git init -b main /myrepo")
    assert auto_container_per_test.connection.file("/myrepo/.git/HEAD").exists
    out = auto_container_per_test.connection.check_output(
        "git -C /myrepo status"
    )
    assert "On branch main" in out
    assert "No commits yet" in out
    assert "nothing to commit" in out
