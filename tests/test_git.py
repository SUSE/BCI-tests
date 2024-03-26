"""This module contains the tests for the git container, the image with git pre-installed.
"""
import pytest
from pytest_container.container import container_and_marks_from_pytest_param
from pytest_container.container import DerivedContainer
from pytest_container.container import ImageFormat
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import GIT_CONTAINER

CONTAINER_IMAGES = (GIT_CONTAINER,)

_priv_key = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACDJMR7NW+gNZGborupz8XoZEjuKRuKjLzVPAwfPcjrTzQAAAIi/QgI2v0IC
NgAAAAtzc2gtZWQyNTUxOQAAACDJMR7NW+gNZGborupz8XoZEjuKRuKjLzVPAwfPcjrTzQ
AAAEBACrN2+98i3BPX40CQxih8gRePIokGrmrobXVnNja+XckxHs1b6A1kZuiu6nPxehkS
O4pG4qMvNU8DB89yOtPNAAAAA0JDSQEC
-----END OPENSSH PRIVATE KEY-----"""

_pub_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMkxHs1b6A1kZuiu6nPxehkSO4pG4qMvNU8DB89yOtPN BCI"

_ssh_port = 22022

_git_server_containerfile = rf"""
RUN zypper -n in git-core openssh-server openssh-clients
RUN ssh-keygen -A
RUN useradd -U -m -p "*" git

RUN mkdir /home/git/.ssh && touch /home/git/.ssh/authorized_keys
RUN chmod 700 /home/git/.ssh && chmod 600 /home/git/.ssh/authorized_keys
RUN chown -R git:git /home/git/.ssh
RUN echo "{_pub_key}" >> /home/git/.ssh/authorized_keys

RUN mkdir -p /srv/git/project.git
RUN git -C /srv/git/project.git init --bare

RUN echo -e '\
Port {_ssh_port}\n\
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

EXPOSE {_ssh_port}

CMD ["/usr/sbin/sshd", "-De"]

HEALTHCHECK --interval=5s --timeout=5s --retries=5 CMD ["/usr/bin/ssh-keyscan", "-vvv", "-H", "-p", "{_ssh_port}", "127.0.0.1"]
"""


def test_git_version(auto_container):
    assert "git version 2." in auto_container.connection.check_output(
        "git --version"
    )


def test_git_clone_https(auto_container_per_test):
    """Test that we can clone a repository over HTTPS successfully."""
    auto_container_per_test.connection.check_output(
        "git clone https://github.com/github/gemoji.git /gemoji"
    )
    auto_container_per_test.connection.file("/gemoji/.git/HEAD").exists
    auto_container_per_test.connection.file("/gemoji/Gemfile").exists
    auto_container_per_test.connection.file("/gemoji/db/emoji.json").exists
    out = auto_container_per_test.connection.check_output(
        "git -C /gemoji status"
    )
    assert "Your branch is up to date" in out
    assert "nothing to commit, working tree clean" in out


GIT_SERVER_CONTAINER = DerivedContainer(
    base="registry.suse.com/bci/bci-base:latest",
    containerfile=_git_server_containerfile,
    image_format=ImageFormat.DOCKER,
    extra_launch_args=["--cap-add", "AUDIT_WRITE"],
)

_git_container, _marks = container_and_marks_from_pytest_param(GIT_CONTAINER)

GIT_POD = pytest.param(
    Pod(
        containers=[
            GIT_SERVER_CONTAINER,
            _git_container,
        ],
    ),
    marks=_marks,
)


@pytest.mark.parametrize("pod_per_test", [GIT_POD], indirect=True)
def test_git_clone_ssh(pod_per_test: PodData) -> None:
    """Test that we can clone a repository over SSH successfully."""
    cli = pod_per_test.container_data[1].connection
    srv = pod_per_test.container_data[0]
    host = srv.inspect.network.ip_address or "127.0.0.1"

    cli.check_output(f"mkdir /root/.ssh")
    cli.check_output(f'echo -e "{_priv_key}" > /root/.ssh/id_ed25519')
    cli.check_output("chmod 0600 /root/.ssh/id_ed25519")
    cli.check_output("eval `ssh-agent -s` && ssh-add /root/.ssh/id_ed25519")
    cli.check_output(
        f"ssh-keyscan -vvv -p {_ssh_port} {host} >> /root/.ssh/known_hosts"
    )

    cli.check_output(
        f"git clone ssh://git@{host}:{_ssh_port}/srv/git/project.git /project"
    )
    cli.file("/project/.git/HEAD").exists
    out = cli.check_output("git -C /project status")

    assert "No commits yet" in out
    assert "nothing to commit" in out


def test_git_init(auto_container_per_test):
    """Test that we can init a repository successfully."""
    auto_container_per_test.connection.check_output("git init -b main /myrepo")
    auto_container_per_test.connection.file("/myrepo/.git/HEAD").exists
    out = auto_container_per_test.connection.check_output(
        "git -C /myrepo status"
    )
    assert "On branch main" in out
    assert "No commits yet" in out
    assert "nothing to commit" in out
