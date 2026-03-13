#!/usr/bin/env python3
"""Build the Windows .exe with PyInstaller."""

import PyInstaller.__main__
import platform

args = [
    "nms_expeditions_online/__main__.py",
    "--onefile",
    "--console",
    "--name", "NMSExpeditionsOnline",
]

# Request admin on Windows
if platform.system() == "Windows":
    args.append("--uac-admin")

PyInstaller.__main__.run(args)
