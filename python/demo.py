from __future__ import annotations

from python.models import BacklogTask, ProjectBacklog, ProjectIdea, TaskStatus
from python.storage import ForgeStorage

DEMO_SLUG = "demo-dashboard"


def _demo_backlog() -> ProjectBacklog:
    return ProjectBacklog(
        project_slug=DEMO_SLUG,
        tasks=[
            BacklogTask(
                id="T-demo0001",
                title="Initialize repository",
                description="Create README, folders, and project metadata.",
                status=TaskStatus.DONE,
                priority=90,
                test_command="echo ok",
            ),
            BacklogTask(
                id="T-demo0002",
                title="Add dashboard API",
                description="Aggregate ideas, backlogs, and test runs for the UI.",
                status=TaskStatus.IN_PROGRESS,
                priority=85,
            ),
            BacklogTask(
                id="T-demo0003",
                title="Wire task status controls",
                description="Allow start/done transitions from the browser.",
                status=TaskStatus.BACKLOG,
                priority=80,
                depends_on=["T-demo0002"],
            ),
            BacklogTask(
                id="T-demo0004",
                title="Document roadmap progress",
                description="Update README and ship the dashboard milestone.",
                status=TaskStatus.BACKLOG,
                priority=70,
            ),
        ],
    )


def _demo_idea() -> ProjectIdea:
    return ProjectIdea(
        slug=DEMO_SLUG,
        title="Demo Dashboard Project",
        summary="Sample forged project to explore the AityUahn dashboard and backlog UI.",
        vision="Show progress bars, task statuses, and test history without calling AI providers.",
        constraints=["Local-only demo data", "Safe to delete from .python/backlogs/"],
        success_criteria=["Dashboard loads with mixed task statuses", "Task actions update progress"],
        tags=["demo", "dashboard"],
    )


def demo_dashboard_payload() -> dict:
    """Dashboard JSON for GitHub Pages static demo (matches GET /api/dashboard shape)."""
    idea = _demo_idea()
    backlog = _demo_backlog()
    progress = backlog.progress
    return {
        "workspace": "(GitHub Pages demo)",
        "forge_data": "(static demo-data.json + browser storage)",
        "summary": {
            "projects": 1,
            "tasks": progress["total"],
            "done": progress["done"],
            "percent": progress["percent"],
        },
        "projects": [
            {
                "slug": DEMO_SLUG,
                "title": idea.title,
                "summary": idea.summary,
                "tags": idea.tags,
                "registered": True,
                "progress": progress,
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status.value,
                        "priority": t.priority,
                    }
                    for t in sorted(backlog.tasks, key=lambda x: (-x.priority, x.created_at))
                ],
                "last_test": None,
            }
        ],
    }


def seed_demo_data(storage: ForgeStorage) -> str:
    """Create a sample idea + backlog for UI demos when forge data is empty."""
    if storage.backlog_path(DEMO_SLUG).is_file():
        return DEMO_SLUG

    idea = _demo_idea()
    storage.save_idea(idea)
    storage.save_backlog(_demo_backlog())
    storage.register_project(DEMO_SLUG, idea.title)
    return DEMO_SLUG
