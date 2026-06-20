"""One-shot local + live diagnostics for `aityuahn checkup`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from python.forge import LForge
from python.saas.health import app_version
from python.status_report import build_status_report
from python.verify_setup import run_verification


@dataclass
class CheckupReport:
    version: str
    ok: bool
    forge_url: str
    saas_url: str | None
    local: dict[str, Any]
    checks: list[dict[str, Any]] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "ok": self.ok,
            "forge_url": self.forge_url,
            "saas_url": self.saas_url,
            "local": self.local,
            "checks": self.checks,
            "hints": self.hints,
        }


def run_checkup(forge: LForge, forge_url: str, saas_url: str | None = None) -> CheckupReport:
    status = build_status_report(forge, forge_url, saas_url)
    verification = run_verification(forge_url, saas_url)
    checks = [
        {"name": c.name, "ok": c.ok, "detail": c.detail, **({"data": c.data} if c.data else {})}
        for c in verification.checks
    ]
    hints: list[str] = []
    if not status.forge_reachable:
        hints.append("Start the forge: aityuahn serve --demo --open")
        hints.append("Then run: aityuahn wait && aityuahn ping -q")
    if saas_url and status.saas_reachable is False:
        hints.append("Check Vercel env: DATABASE_URL and AITYUAHN_JWT_SECRET")
    enabled = [p for p in forge.config.providers if p.enabled]
    if not enabled:
        hints.append("No AI providers enabled — edit forge.yaml and .env for forge/agents")

    return CheckupReport(
        version=app_version(),
        ok=verification.ok and bool(enabled or status.forge_reachable),
        forge_url=forge_url,
        saas_url=saas_url,
        local=status.to_dict(),
        checks=checks,
        hints=hints,
    )
