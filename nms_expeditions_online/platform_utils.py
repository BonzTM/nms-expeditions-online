import os
import platform
import sys


def is_windows() -> bool:
    return platform.system() == "Windows"


def _system32_path(exe_name: str) -> str:
    """Return the full path to an executable in System32, avoiding search-order hijacking."""
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return os.path.join(system_root, "System32", exe_name)


def is_admin() -> bool:
    if is_windows():
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    return os.getuid() == 0


def require_admin() -> None:
    if is_admin():
        return
    if is_windows():
        import ctypes
        import subprocess
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, subprocess.list2cmdline(sys.argv), None, 1
        )
        if result <= 32:
            print("ERROR: Failed to elevate to administrator.")
            sys.exit(1)
        sys.exit(0)
    else:
        print("ERROR: This program must be run as root (sudo).")
        sys.exit(1)


def get_app_dir() -> str:
    """Get the directory where the exe (or script) lives."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_hosts_path() -> str:
    if is_windows():
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


