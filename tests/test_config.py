from pathlib import Path

from python.config import load_forge_config


def test_load_example_config():
    path = Path(__file__).resolve().parent.parent / "config" / "forge.example.yaml"
    cfg = load_forge_config(path)
    assert cfg.default_provider == "claude"
    assert any(p.id == "cursor" for p in cfg.providers)
