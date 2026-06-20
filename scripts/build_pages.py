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
# Empty = relative asset paths (works on custom domain and github.io/Repo/).
# Set GITHUB_PAGES_BASE=/AityUahn/ only for legacy absolute subpath builds.
PAGES_BASE = os.environ.get("GITHUB_PAGES_BASE", "")
PAGES_CUSTOM_DOMAIN = os.environ.get("AITYUAHN_PAGES_DOMAIN", "aityuahn.hyperlinks.space")


def _patch_html(html: str) -> str:
    """Strip forge /static/ prefix; use relative URLs so custom domains at / work."""
    html = html.replace("/static/", "")
    if not PAGES_BASE or PAGES_BASE in ("/", "./"):
        return html
    base = PAGES_BASE if PAGES_BASE.endswith("/") else f"{PAGES_BASE}/"
    if "<base " not in html:
        html = html.replace("<head>", f'<head>\n  <base href="{base}">', 1)
    html = re.sub(r'href="(?!https?://|#|/)([^"]+)"', rf'href="{base}\1"', html)
    html = re.sub(r'src="(?!https?://|/)([^"]+)"', rf'src="{base}\1"', html)
    return html


def build_pages() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    config = json.loads((STATIC / "config.json").read_text(encoding="utf-8"))
    config["pagesBase"] = PAGES_BASE or "/"
    if PAGES_CUSTOM_DOMAIN:
        config["siteUrl"] = f"https://{PAGES_CUSTOM_DOMAIN.strip()}"
    (DOCS / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    for name in ("landing.html", "controller.html", "docs.html", "guide.html"):
        dst = DOCS / ("index.html" if name == "landing.html" else name)
        dst.write_text(_patch_html((STATIC / name).read_text(encoding="utf-8")), encoding="utf-8")

    for name in ("app.js", "auth.js", "landing.js", "setup.js", "styles.css", "landing.css", "logo.svg"):
        src = STATIC / name
        if src.is_file():
            shutil.copy2(src, DOCS / name)

    (DOCS / "demo-data.json").write_text(
        json.dumps(demo_dashboard_payload(), indent=2),
        encoding="utf-8",
    )
    (DOCS / ".nojekyll").touch()
    if PAGES_CUSTOM_DOMAIN:
        (DOCS / "CNAME").write_text(PAGES_CUSTOM_DOMAIN.strip() + "\n", encoding="utf-8")
    mode = PAGES_BASE or "relative (custom domain + project pages)"
    print(f"Built GitHub Pages site in {DOCS} (base={mode})")


if __name__ == "__main__":
    build_pages()
