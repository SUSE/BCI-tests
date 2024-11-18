"""Module with helper utilities around SELinux."""

from pathlib import Path

try:
    from typing import Literal
except ImportError:
    # typing.Literal is available on python3.8+
    # https://docs.python.org/3/library/typing.html#typing.Literal
    from typing_extensions import Literal


def selinux_status(
    _selinux_sysfs_dir: str = "/sys/fs/selinux/",
) -> Literal["enforcing", "permissive", "disabled"]:
    """Returns the host's SELinux status"""

    selinux_sysfs_dir = Path(_selinux_sysfs_dir)

    if not (
        selinux_sysfs_dir.exists() and (selinux_sysfs_dir / "enforce").exists()
    ):
        return "disabled"

    if (selinux_sysfs_dir / "enforce").read_text().strip() == "1":
        return "enforcing"

    return "permissive"
