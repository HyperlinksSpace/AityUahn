"""Build local + live status summary for `aityuahn status`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from python.forge import LForge
from python.saas.health import app_version
from python.verify_setup import run_verification


@dataclass
class StatusRow:
    key: str
    value: str
    live: bool | None = None  # None = not a probe row


@dataclass
class StatusReport:
    version: str
    rows: list[StatusRow] = field(default_factory=list)
    forge_reachable: bool = False
    saas_reachable: bool | None = None

    @property
    def ok(self) -> bool:
        if not self.forge_reachable:
            return False
        if self.saas_reachable is False:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "ok": self.ok,
            "forge_reachable": self.forge_reachable,
            "saas_reachable": self.saas_reachable,
            "rows": [{"key": r.key, "value": r.value, "live": r.live} for r in self.rows],
        }


def build_status_report(
    forge: LForge,
    forge_url: str,
    saas_url: str | None = None,
) -> StatusReport:
    enabled = [p.id for p in forge.config.providers if p.enabled]
    report = StatusReport(
        version=app_version(),
        rows=[
            StatusRow("workspace", str(forge.config.workspace_root)),
            StatusRow("forge_data", str(forge.config.forge_data_dir)),
            StatusRow("default_provider", forge.config.default_provider or "—"),
            StatusRow("providers", ", ".join(enabled) if enabled else "none enabled"),
        ],
    )

    verification = run_verification(forge_url, saas_url)
    for check in verification.checks:
        report.rows.append(
            StatusRow(
                check.name,
                check.detail,
                live=check.ok,
            )
        )
        if check.name == "forge":
            report.forge_reachable = check.ok
        elif check.name == "saas":
            report.saas_reachable = check.ok

    return report
