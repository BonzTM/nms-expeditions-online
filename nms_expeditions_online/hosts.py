"""Hosts file management — install/uninstall NMS server redirects."""

from nms_expeditions_online.platform_utils import get_hosts_path

SENTINEL_START = "# NMS-EXPEDITIONS-ONLINE-START"
SENTINEL_END = "# NMS-EXPEDITIONS-ONLINE-END"

HOSTS_ENTRIES = [
    "127.0.0.1 merged-nms-auth.nomanssky.com",
    "127.0.0.1 merged-nms-static.nomanssky.com",
    "127.0.0.1 merged-nms-discovery.nomanssky.com",
    "127.0.0.1 merged-nms-contentreport.nomanssky.com",
]


def is_installed() -> bool:
    """Check if the hosts file has our entries."""
    try:
        with open(get_hosts_path(), "r") as f:
            return SENTINEL_START in f.read()
    except Exception:
        return False


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
        with open(hosts_path, "w") as f:
            f.write(content)
    except PermissionError:
        return "Permission denied writing hosts file. Run as administrator."

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
        with open(hosts_path, "w") as f:
            f.write(content)
    except PermissionError:
        return "Permission denied writing hosts file. Run as administrator."

    return None
