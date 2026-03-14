#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
    echo "This tool requires root privileges (hosts file + port 443)."
    echo "Re-running with sudo..."
    exec sudo -E "$0" "$@"
fi

# Check for Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Install it with your package manager, e.g.:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.minor}")')
if [ "$PYTHON_VERSION" -lt 10 ]; then
    echo "ERROR: Python 3.10+ is required (found 3.$PYTHON_VERSION)."
    exit 1
fi

# Install cryptography if missing
if ! python3 -c "import cryptography" &>/dev/null; then
    echo "Installing required package: cryptography..."
    pip3 install cryptography
fi

# Run the app
cd "$(dirname "$0")"
python3 -m nms_expeditions_online
