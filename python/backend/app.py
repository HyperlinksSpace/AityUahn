"""App factory — local forge (default) or combined dev monolith."""

from __future__ import annotations

from fastapi import FastAPI

from python.backend.forge_app import create_forge_app
from python.forge import LForge
from python.saas.router import create_saas_router


def create_app(
    forge: LForge | None = None,
    *,
    include_saas: bool = False,
    serve_ui: bool = True,
) -> FastAPI:
    """Build API app.

    - ``include_saas=False`` (default): local forge utility — ``aityuahn serve``.
    - ``include_saas=True``: forge + SaaS on one port (local dev only).
    """
    engine = forge or LForge()
    if not include_saas:
        return create_forge_app(engine, serve_ui=serve_ui)

    saas_router, ton_service = create_saas_router(engine)
    app = create_forge_app(engine, serve_ui=serve_ui)
    app.title = "AityUahn (combined)"
    app.include_router(saas_router)

    @app.on_event("startup")
    async def _start_ton_poll() -> None:
        ton_service.start_background_poll()

    return app
