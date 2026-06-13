import os

from fastapi.testclient import TestClient

from python.backend.saas_app import create_saas_app
from python.saas.health import jwt_configured, saas_health


def test_saas_health_local_json_mode(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AITYUAHN_JWT_SECRET", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)

    payload = saas_health(serverless=False)
    assert payload["ok"] is True
    assert payload["role"] == "saas"
    assert payload["storage"] == "json"
    assert payload["jwt_configured"] is False
    assert "warnings" in payload


def test_saas_health_serverless_requires_neon_and_jwt(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AITYUAHN_JWT_SECRET", raising=False)

    payload = saas_health(serverless=True)
    assert payload["ok"] is False
    assert "DATABASE_URL not set" in payload["issues"]
    assert any("AITYUAHN_JWT_SECRET" in issue for issue in payload["issues"])


def test_saas_health_serverless_ok(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("AITYUAHN_JWT_SECRET", "x" * 32)
    monkeypatch.setattr("python.saas.health.ping_database", lambda dsn, **kw: True)

    payload = saas_health(serverless=True)
    assert payload["ok"] is True
    assert payload["storage"] == "neon"
    assert payload["jwt_configured"] is True
    assert payload["database_reachable"] is True


def test_saas_health_endpoint_local():
    client = TestClient(create_saas_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "saas"
    assert body["ok"] is True
    assert "version" in body


def test_jwt_configured_length(monkeypatch):
    monkeypatch.setenv("AITYUAHN_JWT_SECRET", "short")
    assert jwt_configured() is False
    monkeypatch.setenv("AITYUAHN_JWT_SECRET", "a" * 32)
    assert jwt_configured() is True
    monkeypatch.delenv("AITYUAHN_JWT_SECRET", raising=False)
    assert jwt_configured() is False
