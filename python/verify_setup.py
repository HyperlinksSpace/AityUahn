"""Shared forge + SaaS connectivity checks for doctor and verify CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] | None = None


@dataclass
class VerificationReport:
    forge_url: str
    saas_url: str | None = None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if not c.ok)


def run_verification(
    forge_url: str,
    saas_url: str | None = None,
    *,
    timeout: float = 8.0,
) -> VerificationReport:
    forge_url = forge_url.rstrip("/")
    report = VerificationReport(forge_url=forge_url, saas_url=saas_url)

    with httpx.Client(timeout=timeout) as client:
        try:
            r = client.get(f"{forge_url}/api/health", headers={"Accept": "application/json"})
            if r.status_code == 200:
                body = r.json()
                ok = body.get("ok") is True and body.get("role") == "forge"
                detail = f"{forge_url}/api/health"
                if not ok and body.get("role"):
                    detail += f" (role={body.get('role')})"
                report.checks.append(CheckResult("forge", ok, detail, body))
            else:
                report.checks.append(
                    CheckResult("forge", False, f"HTTP {r.status_code} from {forge_url}/api/health")
                )
        except httpx.HTTPError as exc:
            report.checks.append(CheckResult("forge", False, f"Could not reach forge: {exc}"))

        if saas_url:
            saas_url = saas_url.rstrip("/")
            report.saas_url = saas_url
            try:
                r = client.get(f"{saas_url}/api/health", headers={"Accept": "application/json"})
                if r.status_code == 200:
                    body = r.json()
                    ok = body.get("ok") is True and body.get("role") == "saas"
                    issues = body.get("issues") or []
                    detail = f"{saas_url}/api/health"
                    if issues:
                        detail += " — " + "; ".join(str(i) for i in issues)
                    report.checks.append(CheckResult("saas", ok, detail, body))
                else:
                    report.checks.append(
                        CheckResult("saas", False, f"HTTP {r.status_code} from {saas_url}/api/health")
                    )
            except httpx.HTTPError as exc:
                report.checks.append(CheckResult("saas", False, f"Could not reach SaaS: {exc}"))

    return report
