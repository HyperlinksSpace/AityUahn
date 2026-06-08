from pathlib import Path

from fastapi.testclient import TestClient

from python.backend.app import create_app
from python.config import load_forge_config
from python.forge import LForge
from tests.test_api import _test_forge


def test_register_login_and_project(tmp_path: Path):
    forge = _test_forge(tmp_path)
    client = TestClient(create_app(forge))

    r = client.post(
        "/api/saas/auth/register",
        json={"email": "lead@acme.com", "password": "secret12", "name": "Lead", "plan": "team"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/saas/projects",
        headers=headers,
        json={"name": "Acme App", "slug": "acme-app", "create_demo": True},
    )
    assert r.status_code == 200
    project = r.json()
    assert project["slug"] == "acme-app"

    r = client.post(
        "/api/saas/auth/register",
        json={"email": "dev@acme.com", "password": "secret12", "name": "Dev", "plan": "personal"},
    )
    assert r.status_code == 200

    r = client.post(
        f"/api/saas/projects/{project['id']}/members",
        headers=headers,
        json={"email": "dev@acme.com", "role": "member"},
    )
    assert r.status_code == 200
    assert len(r.json()["roster"]) == 2

    dev_token = client.post(
        "/api/saas/auth/login",
        json={"email": "dev@acme.com", "password": "secret12"},
    ).json()["access_token"]
    r = client.get("/api/saas/projects", headers={"Authorization": f"Bearer {dev_token}"})
    assert len(r.json()) == 1


def test_personal_plan_project_limit(tmp_path: Path):
    forge = _test_forge(tmp_path)
    client = TestClient(create_app(forge))
    r = client.post(
        "/api/saas/auth/register",
        json={"email": "solo@home.com", "password": "secret12", "plan": "personal"},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/api/saas/projects", headers=headers, json={"name": "One", "slug": "one"})
    r = client.post("/api/saas/projects", headers=headers, json={"name": "Two", "slug": "two"})
    assert r.status_code == 400


def test_pricing_public(tmp_path: Path):
    forge = _test_forge(tmp_path)
    client = TestClient(create_app(forge))
    r = client.get("/api/saas/pricing")
    assert r.status_code == 200
    plans = r.json()
    assert len(plans) == 2
    team = next(p for p in plans if p["id"] == "team")
    assert "TON" in team["price_label"]
    assert team.get("payment_method") == "ton"
