import os
import platform
import sys


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_admin() -> bool:
    if is_windows():
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    return os.getuid() == 0


def require_admin():
    if is_admin():
        return
    if is_windows():
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
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
