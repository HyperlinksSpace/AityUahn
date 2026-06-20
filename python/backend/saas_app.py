"""Cloud SaaS API — auth, teams, billing. Intended for Vercel + Neon (no local forge)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from python.forge import LForge
from python.api_info import saas_info
from python.saas.health import app_version, saas_health
from python.saas.router import create_saas_router


def create_saas_app(forge: LForge | None = None) -> FastAPI:
    """SaaS-only app for hosted deployment (Vercel/Railway). Forge execution stays on user machines."""
    engine = forge or LForge()
    saas_router, ton_service = create_saas_router(engine)
    serverless = os.environ.get("VERCEL") == "1"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not serverless:
            ton_service.start_background_poll()
        yield

    app = FastAPI(title="AityUahn Cloud", version=app_version(), lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(saas_router)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return saas_health(serverless=serverless)

    @app.get("/api/ready")
    def ready() -> dict[str, Any]:
        health = saas_health(serverless=serverless)
        return {
            "ready": health.get("ok") is True,
            "role": "saas",
            "version": app_version(),
        }

    @app.get("/api/info")
    def info() -> dict[str, Any]:
        return saas_info(serverless=serverless)

    @app.get("/api/cron/ton-poll")
    async def cron_ton_poll(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        """Vercel Cron entry — replaces background TON poll on serverless."""
        secret = os.environ.get("CRON_SECRET", "").strip()
        if secret:
            expected = f"Bearer {secret}"
            if authorization != expected:
                raise HTTPException(401, "Invalid cron secret")
        await ton_service.poll_once()
        return {"ok": True}

    return app
