#!/usr/bin/env python3
"""Run SaaS schema migrations against DATABASE_URL (Vercel build step)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    if os.environ.get("SKIP_DB_MIGRATE") == "1":
        print("[db] SKIP_DB_MIGRATE=1 — skipping migrations")
        return 0
    try:
        from python.saas.db.migrate import run_migrations

        print("[db] Running schema migrations against DATABASE_URL...")
        run_migrations()
        print("[db] Schema is up to date.")
        return 0
    except Exception as exc:
        print(f"[db] Migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
