#!/usr/bin/env python3
"""Console entry for aityuahn-installer.exe (PyInstaller one-file)."""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from scripts.installer_core import run_install


def main() -> int:
    try:
        run_install()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        input("\nPress Enter to exit...")
        return 1
    input("\nPress Enter to exit...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
