#!/usr/bin/env python3
"""Build the Windows .exe with the same PyInstaller options used in CI."""

import PyInstaller.__main__
import platform

args = [
    "nms_expeditions_online/__main__.py",
    "--clean",
    "--onefile",
    "--console",
    "--collect-submodules",
    "cryptography",
    "--name", "NMSExpeditionsOnline",
]

# Request admin on Windows
if platform.system() == "Windows":
    args.append("--uac-admin")

PyInstaller.__main__.run(args)
