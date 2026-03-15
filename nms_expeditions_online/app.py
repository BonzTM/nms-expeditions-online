"""Main application — text-based menu for NMS Expedition Proxy."""

import glob
import os

from nms_expeditions_online import hosts
from nms_expeditions_online import proxy as proxy_module
from nms_expeditions_online.platform_utils import get_app_dir, require_admin

EXPEDITION_FILENAME = "SEASON_DATA_CACHE.JSON"


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def find_expedition_file() -> str | None:
    """Find the expedition JSON file in the app directory."""
    app_dir = get_app_dir()
    # Check for the standard filename first
    path = os.path.join(app_dir, EXPEDITION_FILENAME)
    if os.path.isfile(path):
        return path
    # Check for any .json file
    json_files = glob.glob(os.path.join(app_dir, "*.json"))
    # Filter out config files
    json_files = [f for f in json_files if os.path.basename(f).lower() not in ("package.json",)]
    if len(json_files) == 1:
        return json_files[0]
    if len(json_files) > 1:
        print(f"Multiple JSON files found in {app_dir}:")
        for i, f in enumerate(json_files, 1):
            print(f"  {i}. {os.path.basename(f)}")
        try:
            choice = input(f"\nSelect expedition file (1-{len(json_files)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(json_files):
                return json_files[idx]
        except (ValueError, EOFError):
            pass
        return None
    return None


def get_expedition_info(path: str) -> dict | None:
    """Read basic info from expedition JSON."""
    import json
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "SeasonId": data.get("SeasonId", "?"),
            "Description": data.get("Description", "Unknown"),
            "file": os.path.basename(path),
        }
    except Exception:
        return None


def print_header() -> None:
    print("=" * 50)
    print("   NMS Expeditions Online")
    print("=" * 50)
    print()


def print_status() -> None:
    installed = hosts.is_installed()
    print(f"  Hosts file: {'INSTALLED' if installed else 'Not installed'}")

    exp_file = find_expedition_file()
    if exp_file:
        info = get_expedition_info(exp_file)
        if info:
            print(f"  Expedition:  {info['file']} (SeasonId={info['SeasonId']})")
        else:
            print(f"  Expedition:  {os.path.basename(exp_file)} (could not read)")
    else:
        print("  Expedition:  No JSON file found")

    print()


def do_install() -> None:
    clear_screen()
    print_header()
    print("--- Install ---\n")

    exp_file = find_expedition_file()
    if not exp_file:
        app_dir = get_app_dir()
        print("No expedition JSON file found!\n")
        print("Download your expedition from:")
        print("  https://cwmonkey.github.io/nms-expeditions/\n")
        print("Place the downloaded SEASON_DATA_CACHE.JSON file in:")
        print(f"  {app_dir}\n")
        input("Press Enter to return to menu...")
        return

    if hosts.is_installed():
        print("Already installed.\n")
        input("Press Enter to return to menu...")
        return

    info = get_expedition_info(exp_file)
    if info:
        print(f"Expedition: {info['file']} (SeasonId={info['SeasonId']})\n")

    print("This will modify your system hosts file to redirect")
    print("No Man's Sky API traffic through the local proxy.\n")
    print("The following entries will be added:\n")
    for entry in hosts.HOSTS_ENTRIES:
        print(f"  {entry}")
    print()

    try:
        confirm = input("Continue? (y/n): ").strip().lower()
    except EOFError:
        return
    if confirm != "y":
        return

    err = hosts.install()
    if err:
        print(f"\nERROR: {err}")
        input("\nPress Enter to return to menu...")
        return

    print("\nHosts file updated successfully.")
    input("\nPress Enter to return to menu...")


def do_uninstall() -> None:
    clear_screen()
    print_header()
    print("--- Uninstall ---\n")

    if not hosts.is_installed():
        print("Not currently installed.\n")
        input("Press Enter to return to menu...")
        return

    print("!!! WARNING !!!\n")
    print("If you are in the middle of an expedition, uninstalling")
    print("will prevent you from continuing that expedition save.")
    print("Your expedition progress will be LOST.\n")
    print("Make sure you have completed or abandoned your expedition")
    print("before uninstalling.\n")

    try:
        confirm = input("Type 'uninstall' to confirm: ").strip().lower()
    except EOFError:
        return
    if confirm != "uninstall":
        print("\nUninstall cancelled.")
        input("\nPress Enter to return to menu...")
        return

    err = hosts.uninstall()
    if err:
        print(f"\nERROR: {err}")
        input("\nPress Enter to return to menu...")
        return

    print("\nHosts file restored successfully.")
    input("\nPress Enter to return to menu...")


def do_run() -> None:
    clear_screen()
    print_header()
    print("--- Start Proxy ---\n")

    if not hosts.is_installed():
        print("Hosts file not installed. Please install first.\n")
        input("Press Enter to return to menu...")
        return

    exp_file = find_expedition_file()
    if not exp_file:
        print("No expedition JSON file found.\n")
        input("Press Enter to return to menu...")
        return

    print("Starting proxy server...\n")
    try:
        thread, stop_event, crl_server = proxy_module.start_proxy(exp_file, port=443)
    except Exception as e:
        print(f"\nERROR: {e}")
        input("\nPress Enter to return to menu...")
        return

    # Give the proxy a moment to start
    import time
    time.sleep(2)

    if not thread.is_alive():
        print("\nProxy failed to start. Check errors above.")
        input("\nPress Enter to return to menu...")
        return

    if os.name == "nt":
        print("Installing proxy CA certificate...")
        if proxy_module.install_ca_cert():
            print("  CA certificate installed into trusted root store.")
        else:
            print("  WARNING: Failed to install CA certificate.")
            print("  The game may not trust the proxy's TLS certificates.")

    print("\nRunning self-test...")
    problems = proxy_module.verify_proxy(port=443)
    if problems:
        print("\n  PROBLEMS DETECTED:\n")
        for p in problems:
            for line in p.split("\n"):
                print(f"    {line}")
            print()
        print("  The proxy is running but the game may not connect.")
        print("  Fix the issues above, or press Enter to continue anyway.\n")
    else:
        print("  Self-test passed: proxy is reachable and TLS is working.\n")

    print("=" * 50)
    print("  Proxy is running!")
    print("  Launch No Man's Sky and enjoy your expedition.")
    print("=" * 50)
    print("\nPress Enter to stop the proxy...\n")

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass

    print("Stopping proxy...")
    stop_event.set()
    thread.join(timeout=5)
    if crl_server is not None:
        crl_server.shutdown()
        crl_server.server_close()
    proxy_module.uninstall_ca_cert()
    print("Proxy stopped.\n")
    input("Press Enter to return to menu...")


def main() -> None:
    require_admin()

    while True:
        clear_screen()
        print_header()
        print_status()

        print("  1. Install (set up hosts file)")
        print("  2. Run (start proxy server)")
        print("  3. Uninstall (restore hosts file)")
        print("  4. Exit")
        print()

        try:
            choice = input("Choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            do_install()
        elif choice == "2":
            do_run()
        elif choice == "3":
            do_uninstall()
        elif choice == "4":
            break
        else:
            continue

    # Clean shutdown
    print("Goodbye!")
