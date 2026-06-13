"""SaaS deployment health checks (Vercel + Neon readiness)."""

from __future__ import annotations

import os
from importlib.metadata import version
from typing import Any


def app_version() -> str:
    try:
        return version("aityuahn")
    except Exception:
        return "0.0.0"


def jwt_configured() -> bool:
    secret = os.environ.get("AITYUAHN_JWT_SECRET", "").strip()
    return len(secret) >= 32


def ping_database(dsn: str, *, timeout: int = 5) -> bool:
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=timeout) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def saas_health(*, serverless: bool) -> dict[str, Any]:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    storage = "neon" if dsn else "json"
    jwt_ok = jwt_configured()
    db_reachable: bool | None = ping_database(dsn) if dsn else None

    warnings: list[str] = []
    issues: list[str] = []

    if serverless:
        if not dsn:
            issues.append("DATABASE_URL not set")
        if not jwt_ok:
            issues.append("AITYUAHN_JWT_SECRET not set or shorter than 32 characters")
        if dsn and db_reachable is False:
            issues.append("database unreachable")
    elif not jwt_ok:
        warnings.append("AITYUAHN_JWT_SECRET not set — using dev default")

    payload: dict[str, Any] = {
        "ok": len(issues) == 0,
        "role": "saas",
        "version": app_version(),
        "serverless": serverless,
        "storage": storage,
        "jwt_configured": jwt_ok,
        "database_reachable": db_reachable,
    }
    if warnings:
        payload["warnings"] = warnings
    if issues:
        payload["issues"] = issues
    return payload
