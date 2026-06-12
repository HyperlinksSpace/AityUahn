"""Smoke tests for installer build script (no PyInstaller run in CI by default)."""

from pathlib import Path


def test_build_installer_script_exists():
    root = Path(__file__).resolve().parent.parent
    assert (root / "scripts" / "build_installer.py").is_file()
    assert (root / "scripts" / "installer_core.py").is_file()
    assert (root / "scripts" / "installer_main.py").is_file()


def test_release_workflow_exists():
    root = Path(__file__).resolve().parent.parent
    wf = root / ".github" / "workflows" / "release-installer.yml"
    assert wf.is_file()
    text = wf.read_text(encoding="utf-8")
    assert "aityuahn-installer.exe" in text
    assert "release-installer.yml" in text or "Windows installer release" in text
