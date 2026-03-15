"""Hosts file management — install/uninstall NMS server redirects."""

import os
import subprocess
import tempfile

from nms_expeditions_online.platform_utils import _system32_path, get_hosts_path, is_windows

SENTINEL_START = "# NMS-EXPEDITIONS-ONLINE-START"
SENTINEL_END = "# NMS-EXPEDITIONS-ONLINE-END"

HOSTS_ENTRIES = [
    "127.0.0.1 merged-nms-auth.nomanssky.com",
    "127.0.0.1 merged-nms-static.nomanssky.com",
    "127.0.0.1 merged-nms-discovery.nomanssky.com",
    "127.0.0.1 merged-nms-contentreport.nomanssky.com",
]


def _atomic_write(path: str, content: str) -> None:
    """Write to a file atomically using temp file + rename.

    This prevents corruption from concurrent edits or interrupted writes.
    The temp file is created in the same directory so os.replace() is atomic
    on the same filesystem.
    """
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".hosts_tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up the temp file if rename failed
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def is_installed() -> bool:
    """Check if the hosts file has our entries."""
    try:
        with open(get_hosts_path(), "r") as f:
            return SENTINEL_START in f.read()
    except Exception:
        return False


def _flush_dns_cache() -> None:
    """Flush the system DNS cache so hosts file changes take effect immediately."""
    if is_windows():
        try:
            subprocess.run(
                [_system32_path("ipconfig.exe"), "/flushdns"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def install() -> str | None:
    """Add NMS redirect entries to the hosts file. Returns error message or None."""
    hosts_path = get_hosts_path()

    if is_installed():
        return None  # already installed

    try:
        with open(hosts_path, "r") as f:
            content = f.read()
    except PermissionError:
        return "Permission denied reading hosts file. Run as administrator."
    except FileNotFoundError:
        content = ""

    block = "\n".join([SENTINEL_START] + HOSTS_ENTRIES + [SENTINEL_END])

    # Ensure we start on a new line
    if content and not content.endswith("\n"):
        content += "\n"
    content += block + "\n"

    try:
        _atomic_write(hosts_path, content)
    except PermissionError:
        return "Permission denied writing hosts file. Run as administrator."

    _flush_dns_cache()
    return None


def uninstall() -> str | None:
    """Remove NMS redirect entries from the hosts file. Returns error message or None."""
    hosts_path = get_hosts_path()

    if not is_installed():
        return None  # nothing to remove

    try:
        with open(hosts_path, "r") as f:
            lines = f.readlines()
    except PermissionError:
        return "Permission denied reading hosts file. Run as administrator."

    # Remove everything between sentinels (inclusive)
    new_lines = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped == SENTINEL_START:
            in_block = True
            continue
        if stripped == SENTINEL_END:
            in_block = False
            continue
        if not in_block:
            new_lines.append(line)

    # Clean up trailing blank lines
    content = "".join(new_lines).rstrip("\n") + "\n"

    try:
        _atomic_write(hosts_path, content)
    except PermissionError:
        return "Permission denied writing hosts file. Run as administrator."

    _flush_dns_cache()
    return None
