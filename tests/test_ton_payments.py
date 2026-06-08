from pathlib import Path

import pytest

from python.saas.models import PaymentStatus, Plan
from python.saas.store import SaaSStore
from python.saas.settings import reset_saas_settings_cache, team_price_nano, team_price_ton
from python.saas.ton import (
    TonPaymentService,
    extract_text_comment,
    is_incoming_deposit,
    payment_deeplink,
)


def test_extract_text_comment_from_message():
    in_msg = {
        "source": "EQsender",
        "value": str(team_price_nano()),
        "message": "550e8400-e29b-41d4-a716-446655440000",
        "msg_data": {"@type": "msg.dataText", "text": ""},
    }
    assert extract_text_comment(in_msg) == "550e8400-e29b-41d4-a716-446655440000"


def test_is_incoming_deposit_rejects_outgoing():
    tx = {
        "utime": 1_700_000_000,
        "in_msg": {"source": "EQsender", "message": "uuid", "msg_data": {"@type": "msg.dataText"}},
        "out_msgs": [{"destination": "EQother"}],
    }
    assert not is_incoming_deposit(tx)


def test_payment_deeplink():
    link = payment_deeplink("UQTestWallet", 10_000_000_000, "pay-123")
    assert link.startswith("ton://transfer/UQTestWallet?")
    assert "amount=10000000000" in link
    assert "text=pay-123" in link


def test_complete_payment_upgrades_user(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AITYUAHN_TON_WALLET_ADDRESS", "UQTestWallet")
    store = SaaSStore(tmp_path / "saas")
    user, _ = store.register("pay@acme.com", "secret12", "Payer", Plan.PERSONAL)
    ton = TonPaymentService(store)
    payment = ton.create_team_payment(user.id)

    tx = {
        "utime": 1_700_000_000,
        "transaction_id": {"lt": 123, "hash": "abc"},
        "in_msg": {
            "source": "EQSender123",
            "value": str(team_price_nano()),
            "message": payment.id,
            "msg_data": {"@type": "msg.dataText"},
        },
        "out_msgs": [],
    }
    assert ton._try_complete_payment(tx)

    updated = store.get_user(user.id)
    assert updated
    assert updated.plan == Plan.TEAM
    completed = store.get_payment(payment.id)
    assert completed
    assert completed.status == PaymentStatus.COMPLETED
    assert completed.sender_address == "EQSender123"


def test_underpaid_deposit_ignored(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AITYUAHN_TON_WALLET_ADDRESS", "UQTestWallet")
    store = SaaSStore(tmp_path / "saas")
    user, _ = store.register("cheap@acme.com", "secret12", "Cheap", Plan.PERSONAL)
    ton = TonPaymentService(store)
    payment = ton.create_team_payment(user.id)

    tx = {
        "utime": 1_700_000_000,
        "transaction_id": {"lt": 1, "hash": "x"},
        "in_msg": {
            "source": "EQSender123",
            "value": str(team_price_nano() - 1),
            "message": payment.id,
            "msg_data": {"@type": "msg.dataText"},
        },
        "out_msgs": [],
    }
    assert not ton._try_complete_payment(tx)
    assert store.get_user(user.id).plan == Plan.PERSONAL


def test_team_payment_api(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient

    from python.backend.app import create_app
    from tests.test_api import _test_forge

    monkeypatch.setenv("AITYUAHN_TON_WALLET_ADDRESS", "UQTestWallet")
    forge = _test_forge(tmp_path)
    client = TestClient(create_app(forge))

    r = client.post(
        "/api/saas/auth/register",
        json={"email": "team@acme.com", "password": "secret12", "plan": "team"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["plan"] == "personal"
    assert body.get("requires_ton_payment") is True
    token = body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/saas/billing/team-payment", headers=headers)
    assert r.status_code == 200
    payment = r.json()
    assert payment["amount_ton"] == team_price_ton()
    assert payment["wallet_address"] == "UQTestWallet"
    assert payment["deeplink"].startswith("ton://transfer/")

    r = client.get(f"/api/saas/billing/team-payment/{payment['payment_id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_saas_yaml_custom_price(tmp_path: Path, monkeypatch):
    config = tmp_path / "saas.yaml"
    config.write_text("team_price_ton: 25\npoll_interval_sec: 5\n", encoding="utf-8")
    monkeypatch.setenv("AITYUAHN_SAAS_CONFIG", str(config))
    reset_saas_settings_cache()
    assert team_price_ton() == 25.0
    assert team_price_nano() == 25_000_000_000
    reset_saas_settings_cache()
    monkeypatch.delenv("AITYUAHN_SAAS_CONFIG", raising=False)


def test_saas_yaml_wallet_address(tmp_path: Path, monkeypatch):
    from python.saas.settings import ton_wallet_address

    config = tmp_path / "saas.yaml"
    config.write_text('ton_wallet_address: "UQFromYaml"\n', encoding="utf-8")
    monkeypatch.setenv("AITYUAHN_SAAS_CONFIG", str(config))
    monkeypatch.delenv("AITYUAHN_TON_WALLET_ADDRESS", raising=False)
    reset_saas_settings_cache()
    assert ton_wallet_address() == "UQFromYaml"
    reset_saas_settings_cache()
    monkeypatch.delenv("AITYUAHN_SAAS_CONFIG", raising=False)
