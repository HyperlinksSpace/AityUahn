#!/usr/bin/env python3
"""Build static site in docs/ for GitHub Pages."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from python.demo import demo_dashboard_payload

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "python" / "static"
DOCS = ROOT / "docs"
PAGES_BASE = os.environ.get("GITHUB_PAGES_BASE", "/AityUahn/")


def _patch_html(html: str) -> str:
    base = PAGES_BASE if PAGES_BASE.endswith("/") else f"{PAGES_BASE}/"
    html = html.replace("/static/", "")
    if "<base " not in html:
        html = html.replace("<head>", f'<head>\n  <base href="{base}">', 1)
    html = re.sub(r'href="(?!https?://|#|/)([^"]+)"', rf'href="{base}\1"', html)
    html = re.sub(r'src="(?!https?://|/)([^"]+)"', rf'src="{base}\1"', html)
    return html


def build_pages() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    config = json.loads((STATIC / "config.json").read_text(encoding="utf-8"))
    config["pagesBase"] = PAGES_BASE
    (DOCS / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    for name in ("landing.html", "controller.html", "docs.html"):
        dst = DOCS / ("index.html" if name == "landing.html" else name)
        dst.write_text(_patch_html((STATIC / name).read_text(encoding="utf-8")), encoding="utf-8")

    for name in ("app.js", "auth.js", "landing.js", "styles.css", "landing.css"):
        src = STATIC / name
        if src.is_file():
            shutil.copy2(src, DOCS / name)

    (DOCS / "demo-data.json").write_text(
        json.dumps(demo_dashboard_payload(), indent=2),
        encoding="utf-8",
    )
    (DOCS / ".nojekyll").touch()
    print(f"Built GitHub Pages site in {DOCS} (base={PAGES_BASE})")


if __name__ == "__main__":
    build_pages()
