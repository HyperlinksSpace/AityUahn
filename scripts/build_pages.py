#!/usr/bin/env python3
"""Build static site in docs/ for GitHub Pages."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from python.demo import demo_dashboard_payload

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "python" / "static"
DOCS = ROOT / "docs"


def build_pages() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "styles.css", "config.json"):
        src = STATIC / name
        dst = DOCS / name
        if name == "index.html":
            text = src.read_text(encoding="utf-8").replace("/static/", "")
            dst.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, dst)
    (DOCS / "demo-data.json").write_text(
        json.dumps(demo_dashboard_payload(), indent=2),
        encoding="utf-8",
    )
    (DOCS / ".nojekyll").touch()
    print(f"Built GitHub Pages site in {DOCS}")


if __name__ == "__main__":
    build_pages()
