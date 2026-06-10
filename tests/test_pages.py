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
    assert (docs / "controller.html").is_file()
    assert (docs / "docs.html").is_file()
    assert (docs / "auth.js").is_file()
    assert (docs / "setup.js").is_file()
    assert (docs / "landing.js").is_file()
    assert (docs / "landing.css").is_file()
    index = (docs / "index.html").read_text(encoding="utf-8")
    assert "Try demo" in index
    assert "Download backend" in index or "docs.html#backend" in index
    docs_html = (docs / "docs.html").read_text(encoding="utf-8")
    assert "Download the backend" in docs_html
    assert "backendZip" in (docs / "config.json").read_text(encoding="utf-8")
    assert '<base href="/AityUahn/">' in index
