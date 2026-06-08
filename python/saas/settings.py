from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PlanCopy(BaseModel):
    name: str
    price_label: str | None = None
    features: list[str] = Field(default_factory=list)


class SaasSettings(BaseModel):
    ton_wallet_address: str = ""
    team_price_ton: float = 10.0
    poll_interval_sec: int = 10
    ton_network: str = "mainnet"
    plans: dict[str, PlanCopy] = Field(default_factory=dict)


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def find_saas_config(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    env_path = os.environ.get("AITYUAHN_SAAS_CONFIG")
    if env_path:
        return Path(env_path)
    for path in (cwd / "saas.yaml", cwd / "config" / "saas.yaml", _REPO_ROOT / "saas.yaml"):
        if path.is_file():
            return path
    raise FileNotFoundError(
        "No saas.yaml found. Create saas.yaml at the project root to configure billing."
    )


def load_saas_settings(config_path: Path | None = None) -> SaasSettings:
    path = config_path or find_saas_config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SaasSettings.model_validate(raw)


@lru_cache(maxsize=1)
def get_saas_settings() -> SaasSettings:
    return load_saas_settings()


def reset_saas_settings_cache() -> None:
    get_saas_settings.cache_clear()


def team_price_ton() -> float:
    env = os.environ.get("AITYUAHN_TON_TEAM_PRICE")
    if env:
        return float(env)
    return get_saas_settings().team_price_ton


def team_price_nano() -> int:
    return int(team_price_ton() * 1_000_000_000)


def poll_interval_sec() -> int:
    env = os.environ.get("AITYUAHN_TON_POLL_INTERVAL")
    if env:
        return int(env)
    return get_saas_settings().poll_interval_sec


def ton_network() -> str:
    env = os.environ.get("AITYUAHN_TON_NETWORK")
    if env:
        return env.strip().lower()
    return get_saas_settings().ton_network.lower()


def ton_wallet_address() -> str | None:
    env = os.environ.get("AITYUAHN_TON_WALLET_ADDRESS", "").strip()
    if env:
        return env
    cfg = get_saas_settings().ton_wallet_address.strip()
    return cfg or None


def team_price_label() -> str:
    return f"{team_price_ton():g} TON"


def plan_copy(plan_id: str) -> PlanCopy | None:
    return get_saas_settings().plans.get(plan_id)
