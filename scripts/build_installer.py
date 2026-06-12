#!/usr/bin/env python3
"""Build aityuahn-installer.exe with PyInstaller (Windows)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "aityuahn-installer.spec"


def main() -> None:
    entry = ROOT / "scripts" / "installer_main.py"
    if not entry.is_file():
        raise SystemExit(f"Missing {entry}")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",
            "--name",
            "aityuahn-installer",
            str(entry),
        ],
        cwd=ROOT,
    )
    exe = DIST / "aityuahn-installer.exe"
    if not exe.is_file():
        raise SystemExit(f"Build failed — {exe} not found")
    print(f"Built {exe} ({exe.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
