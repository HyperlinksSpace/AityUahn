"""Shared /api/info payloads for forge and SaaS APIs."""

from __future__ import annotations

from typing import Any

from python.forge import LForge
from python.saas.health import app_version, jwt_configured, saas_health


def forge_info(engine: LForge) -> dict[str, Any]:
    return {
        "name": "AityUahn Forge",
        "role": "forge",
        "version": app_version(),
        "workspace": str(engine.config.workspace_root),
        "forge_data": str(engine.config.forge_data_dir),
        "default_provider": engine.config.default_provider,
        "providers_enabled": [p.id for p in engine.config.providers if p.enabled],
        "links": {
            "health": "/api/health",
            "info": "/api/info",
            "dashboard": "/api/dashboard",
            "landing": "/",
            "controller": "/controller.html",
            "guide": "/guide.html",
            "docs": "/docs.html",
            "openapi": "/docs",
        },
        "cli": {
            "serve": "Run local forge API + UI",
            "forge": "Idea + backlog + scaffold in one step",
            "status": "Local config + API reachability",
            "verify": "Check forge (and optional cloud) reachability",
            "info": "Fetch this /api/info payload from CLI",
            "dashboard": "Print kanban summary from running forge",
            "open": "Open controller or guide in browser",
        },
    }


def saas_info(*, serverless: bool) -> dict[str, Any]:
    health = saas_health(serverless=serverless)
    return {
        "name": "AityUahn Cloud",
        "role": "saas",
        "version": app_version(),
        "serverless": serverless,
        "storage": health.get("storage"),
        "jwt_configured": jwt_configured(),
        "links": {
            "health": "/api/health",
            "info": "/api/info",
            "pricing": "/api/saas/pricing",
            "register": "/api/saas/auth/register",
            "login": "/api/saas/auth/login",
        },
        "health": health,
    }
