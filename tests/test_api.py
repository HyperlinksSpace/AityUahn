from pathlib import Path

from fastapi.testclient import TestClient

from python.backend.app import create_app
from python.config import load_forge_config
from python.forge import LForge


def test_health_and_ui(tmp_path: Path):
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "forge.example.yaml"
    cfg = load_forge_config(cfg_path)
    cfg.forge_data_dir = tmp_path / ".python"
    cfg.workspace_root = tmp_path / "workspace"
    cfg.forge_data_dir.mkdir(parents=True, exist_ok=True)

    forge = LForge.__new__(LForge)
    forge.config = cfg
    from python.backlog import BacklogService
    from python.ideas import IdeaService
    from python.projects import ProjectService
    from python.storage import ForgeStorage
    from python.testing import TestService

    forge.storage = ForgeStorage(cfg.forge_data_dir, cfg.workspace_root)
    forge.ideas = IdeaService(cfg, forge.storage)
    forge.backlog = BacklogService(cfg, forge.storage)
    forge.projects = ProjectService(cfg, forge.storage)
    forge.testing = TestService(cfg, forge.storage)

    client = TestClient(create_app(forge))
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = client.get("/")
    assert r.status_code == 200
    assert "aityuahn" in r.text.lower()
