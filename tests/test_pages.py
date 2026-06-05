from pathlib import Path

from python.demo import demo_dashboard_payload


def test_demo_dashboard_payload():
    data = demo_dashboard_payload()
    assert data["summary"]["projects"] == 1
    assert data["summary"]["tasks"] == 4
    assert data["projects"][0]["slug"] == "demo-dashboard"


def test_build_pages(tmp_path: Path, monkeypatch):
    from scripts import build_pages

    monkeypatch.setattr(build_pages, "DOCS", tmp_path / "docs")
    build_pages.build_pages()
    docs = tmp_path / "docs"
    assert (docs / "index.html").is_file()
    assert (docs / "app.js").is_file()
    assert (docs / "styles.css").is_file()
    assert (docs / "config.json").is_file()
    assert (docs / "demo-data.json").is_file()
    assert (docs / ".nojekyll").is_file()
    index = (docs / "index.html").read_text(encoding="utf-8")
    assert "/static/" not in index
    assert 'href="styles.css"' in index
