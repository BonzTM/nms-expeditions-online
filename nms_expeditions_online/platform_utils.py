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
        import subprocess
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, subprocess.list2cmdline(sys.argv), None, 1
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


def _find_steam_dirs() -> list[str]:
    """Find all Steam installation directories on the system."""
    import glob as globmod
    steam_dirs = []

    if is_windows():
        # Registry lookup (most reliable on Windows)
        try:
            import winreg
            for reg_path in [r"SOFTWARE\Wow6432Node\Valve\Steam", r"SOFTWARE\Valve\Steam"]:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                    val, _ = winreg.QueryValueEx(key, "InstallPath")
                    winreg.CloseKey(key)
                    if val and os.path.isdir(val):
                        steam_dirs.append(val)
                except OSError:
                    pass
        except ImportError:
            pass

        # Common default paths as fallback
        for env_var in ["ProgramFiles(x86)", "ProgramFiles"]:
            path = os.environ.get(env_var, "")
            if path:
                steam_dirs.append(os.path.join(path, "Steam"))

        # Drive letter scan only if nothing found above
        if not any(os.path.isdir(d) for d in steam_dirs):
            import string
            for letter in string.ascii_uppercase:
                for subdir in ["Steam", r"Program Files\Steam",
                               r"Program Files (x86)\Steam", "SteamLibrary"]:
                    candidate = os.path.join(f"{letter}:\\", subdir)
                    if os.path.isdir(candidate):
                        steam_dirs.append(candidate)
    else:
        # Linux: standard locations
        home = os.path.expanduser("~")
        steam_dirs.extend([
            os.path.join(home, ".local", "share", "Steam"),
            os.path.join(home, ".steam", "steam"),
        ])
        # Scan mounted drives for Steam libraries
        for pattern in ["/mnt/*/Steam", "/mnt/*/SteamLibrary*",
                        "/mnt/*/*/Steam", "/mnt/*/*/SteamLibrary*",
                        "/run/media/*/Steam", "/run/media/*/SteamLibrary*"]:
            steam_dirs.extend(globmod.glob(pattern))

    return steam_dirs


def find_nms_dir() -> str | None:
    """Find the No Man's Sky game installation directory."""
    steam_dirs = _find_steam_dirs()

    # Collect all library paths from each Steam installation's libraryfolders.vdf
    library_paths = []
    for steam_dir in steam_dirs:
        # VDF can be in steamapps/ or config/ depending on Steam version
        for vdf_subpath in ["steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"]:
            vdf = os.path.join(steam_dir, vdf_subpath)
            if os.path.isfile(vdf):
                try:
                    with open(vdf) as f:
                        for line in f:
                            line = line.strip()
                            if '"path"' in line:
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    library_paths.append(parts[3])
                except Exception:
                    pass
        # Also add the Steam dir itself as a potential library
        steamapps = os.path.join(steam_dir, "steamapps")
        if os.path.isdir(steamapps):
            library_paths.append(steam_dir)

    # Search each library for NMS, prefer most recently modified manifest
    seen = set()
    best_dir = None
    best_mtime = 0
    for lib_path in library_paths:
        lib_path = os.path.normpath(lib_path)
        if lib_path in seen:
            continue
        seen.add(lib_path)
        steamapps = os.path.join(lib_path, "steamapps")
        if not os.path.isdir(steamapps):
            steamapps = lib_path
        manifest = os.path.join(steamapps, "appmanifest_275850.acf")
        if os.path.isfile(manifest):
            nms_dir = os.path.join(steamapps, "common", "No Man's Sky")
            if os.path.isdir(nms_dir):
                mtime = os.path.getmtime(manifest)
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_dir = nms_dir

    return best_dir
