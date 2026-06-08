from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from python.forge import LForge
from python.models import TaskStatus
from python.saas.router import create_saas_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class IdeaRequest(BaseModel):
    prompt: str
    slug: str | None = None
    provider_id: str | None = None


class ForgeRequest(BaseModel):
    prompt: str
    slug: str | None = None
    scaffold: bool = True
    generate_backlog: bool = True


class BacklogGenerateRequest(BaseModel):
    slug: str
    context: str = ""
    provider_id: str | None = None


class TaskAddRequest(BaseModel):
    slug: str
    title: str
    description: str = ""


class TaskStatusRequest(BaseModel):
    slug: str
    task_id: str
    status: TaskStatus


class TestRunRequest(BaseModel):
    command: str | None = None


class PromptRequest(BaseModel):
    text: str
    provider_id: str | None = None
    system: str | None = None


def create_app(forge: LForge | None = None) -> FastAPI:
    engine = forge or LForge()
    saas_router, ton_service = create_saas_router(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ton_service.start_background_poll()
        yield

    app = FastAPI(title="AityUahn API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(saas_router)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "workspace": str(engine.config.workspace_root),
            "forge_data": str(engine.config.forge_data_dir),
            "default_provider": engine.config.default_provider,
        }

    @app.get("/api/registry")
    def registry() -> dict[str, Any]:
        return engine.list_all()

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        return engine.dashboard()

    @app.get("/api/providers")
    def providers() -> list[dict[str, Any]]:
        return [
            {
                "id": p.id,
                "kind": p.kind,
                "model": p.model,
                "enabled": p.enabled,
                "default": p.default,
            }
            for p in engine.config.providers
        ]

    @app.get("/api/ideas")
    def list_ideas() -> list[dict[str, Any]]:
        return [i.model_dump(mode="json") for i in engine.storage.list_ideas()]

    @app.get("/api/ideas/{slug}")
    def get_idea(slug: str) -> dict[str, Any]:
        idea = engine.storage.load_idea(slug)
        if not idea:
            raise HTTPException(404, f"Idea '{slug}' not found")
        return idea.model_dump(mode="json")

    @app.get("/api/backlog/{slug}")
    def get_backlog(slug: str) -> dict[str, Any]:
        return engine.backlog.progress_report(slug)

    @app.post("/api/idea")
    async def create_idea(body: IdeaRequest) -> dict[str, Any]:
        idea = await engine.ideas.generate(
            body.prompt, slug=body.slug, provider_id=body.provider_id
        )
        return idea.model_dump(mode="json")

    @app.post("/api/backlog/generate")
    async def generate_backlog(body: BacklogGenerateRequest) -> dict[str, Any]:
        await engine.backlog.generate_from_idea(
            body.slug, extra_context=body.context, provider_id=body.provider_id
        )
        return engine.backlog.progress_report(body.slug)

    @app.post("/api/forge")
    async def forge(body: ForgeRequest) -> dict[str, Any]:
        return await engine.forge_project(
            body.prompt,
            slug=body.slug,
            scaffold=body.scaffold,
            generate_backlog=body.generate_backlog,
        )

    @app.post("/api/task")
    def add_task(body: TaskAddRequest) -> dict[str, Any]:
        task = engine.backlog.add_task(body.slug, body.title, body.description)
        return task.model_dump(mode="json")

    @app.patch("/api/task/status")
    def patch_task_status(body: TaskStatusRequest) -> dict[str, Any]:
        try:
            task = engine.backlog.update_status(body.slug, body.task_id, body.status)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        return task.model_dump(mode="json")

    @app.post("/api/prompt")
    async def agent_prompt(body: PromptRequest) -> dict[str, Any]:
        provider_id = body.provider_id or engine.config.default_provider
        text = await engine.complete_prompt(
            body.text, system=body.system, provider_id=body.provider_id
        )
        return {"text": text, "provider": provider_id}

    @app.post("/api/test/{slug}")
    async def run_tests(slug: str, body: TestRunRequest | None = None) -> dict[str, Any]:
        command = body.command if body else None
        try:
            run = await engine.testing.run(slug, command=command)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {
            "run": run.model_dump(mode="json"),
            "backlog": engine.backlog.progress_report(slug),
            "tests": engine.testing.summary(slug),
        }

    @app.get("/demo-data.json")
    def demo_data() -> dict[str, Any]:
        from python.demo import demo_dashboard_payload

        return demo_dashboard_payload()

    @app.get("/controller.html")
    def controller_html() -> FileResponse:
        return FileResponse(STATIC_DIR / "controller.html")

    @app.get("/landing.html")
    def landing_html() -> FileResponse:
        return FileResponse(STATIC_DIR / "landing.html")

    @app.get("/index.html")
    def index_html() -> FileResponse:
        return FileResponse(STATIC_DIR / "landing.html")

    @app.get("/docs.html")
    def docs_html() -> FileResponse:
        return FileResponse(STATIC_DIR / "docs.html")

    @app.get("/")
    def ui() -> FileResponse:
        landing = STATIC_DIR / "landing.html"
        if landing.is_file():
            return FileResponse(landing)
        index = STATIC_DIR / "controller.html"
        if not index.is_file():
            raise HTTPException(404, "UI not found")
        return FileResponse(index)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app
