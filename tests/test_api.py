from pathlib import Path

from fastapi.testclient import TestClient

from python.backend.app import create_app
from python.config import load_forge_config
from python.demo import seed_demo_data
from python.forge import LForge


def _test_forge(tmp_path: Path) -> LForge:
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
    return forge


def test_health_and_ui(tmp_path: Path):
    forge = _test_forge(tmp_path)
    client = TestClient(create_app(forge))
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = client.get("/")
    assert r.status_code == 200
    assert "agentic" in r.text.lower() or "forge" in r.text.lower()

    r = client.get("/controller.html")
    assert r.status_code == 200
    assert "kanban" in r.text.lower()

    r = client.get("/demo-data.json")
    assert r.status_code == 200
    assert r.json()["projects"][0]["slug"] == "demo-dashboard"


def test_dashboard_and_task_status(tmp_path: Path):
    forge = _test_forge(tmp_path)
    seed_demo_data(forge.storage)
    client = TestClient(create_app(forge))

    r = client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["projects"] == 1
    assert data["summary"]["tasks"] == 4
    assert data["projects"][0]["slug"] == "demo-dashboard"

    r = client.patch(
        "/api/task/status",
        json={"slug": "demo-dashboard", "task_id": "T-demo0003", "status": "in_progress"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"

    r = client.get("/api/dashboard")
    assert r.json()["projects"][0]["progress"]["in_progress"] == 2


def test_run_project_tests(tmp_path: Path):
    forge = _test_forge(tmp_path)
    seed_demo_data(forge.storage)
    project_dir = tmp_path / "workspace" / "demo-dashboard"
    project_dir.mkdir(parents=True)
    client = TestClient(create_app(forge))

    r = client.post("/api/test/demo-dashboard", json={"command": "echo demo-test-ok"})
    assert r.status_code == 200
    body = r.json()
    assert body["run"]["status"] == "passed"
    assert body["run"]["exit_code"] == 0
