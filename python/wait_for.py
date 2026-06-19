"""Poll forge (and optional SaaS) until reachable or timeout."""

from __future__ import annotations

import time

from python.verify_setup import run_verification


def wait_for_services(
    forge_url: str,
    saas_url: str | None = None,
    *,
    timeout: float = 60.0,
    interval: float = 2.0,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        report = run_verification(forge_url, saas_url, timeout=3.0)
        if report.ok:
            return True
        time.sleep(interval)
    return False
