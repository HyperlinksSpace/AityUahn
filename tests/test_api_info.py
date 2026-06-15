from fastapi.testclient import TestClient

from python.api_info import forge_info, saas_info
from python.backend.saas_app import create_saas_app

from tests.test_api import _test_forge


def test_forge_info_endpoint(tmp_path):
    from python.backend.app import create_app

    forge = _test_forge(tmp_path)
    client = TestClient(create_app(forge))
    r = client.get("/api/info")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "forge"
    assert body["links"]["controller"] == "/controller.html"
    assert "version" in body


def test_forge_info_helper(tmp_path):
    forge = _test_forge(tmp_path)
    info = forge_info(forge)
    assert info["role"] == "forge"
    assert "cli" in info


def test_saas_info_local():
    info = saas_info(serverless=False)
    assert info["role"] == "saas"
    assert info["links"]["pricing"] == "/api/saas/pricing"
    assert info["health"]["ok"] is True


def test_saas_info_endpoint():
    client = TestClient(create_saas_app())
    r = client.get("/api/info")
    assert r.status_code == 200
    assert r.json()["role"] == "saas"
