from pathlib import Path

from python.models import ProjectIdea
from python.storage import ForgeStorage, slugify


def test_slugify():
    assert slugify("Hyperlinks Space Program") == "hyperlinks-space-program"


def test_save_load_idea(tmp_path: Path):
    storage = ForgeStorage(tmp_path / "forge", tmp_path / "workspace")
    idea = ProjectIdea(slug="demo", title="Demo", summary="A test project")
    storage.save_idea(idea)
    loaded = storage.load_idea("demo")
    assert loaded is not None
    assert loaded.title == "Demo"


def test_backlog_progress(tmp_path: Path):
    from python.models import BacklogTask, ProjectBacklog, TaskStatus

    storage = ForgeStorage(tmp_path / "forge", tmp_path / "workspace")
    backlog = ProjectBacklog(
        project_slug="demo",
        tasks=[
            BacklogTask(id="T-1", title="One", status=TaskStatus.DONE),
            BacklogTask(id="T-2", title="Two", status=TaskStatus.BACKLOG),
        ],
    )
    storage.save_backlog(backlog)
    loaded = storage.load_backlog("demo")
    assert loaded.progress["percent"] == 50.0
