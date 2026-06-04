from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from python.models import ProjectBacklog, ProjectIdea, utc_now


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "project"


class ForgeStorage:
    """Persists ideas, backlogs, and forge metadata under forge_data_dir."""

    def __init__(self, forge_data_dir: Path, workspace_root: Path) -> None:
        self.forge_data_dir = forge_data_dir
        self.workspace_root = workspace_root
        self.ideas_dir = forge_data_dir / "ideas"
        self.backlogs_dir = forge_data_dir / "backlogs"
        self.registry_file = forge_data_dir / "registry.json"
        for d in (self.ideas_dir, self.backlogs_dir, forge_data_dir / "runs"):
            d.mkdir(parents=True, exist_ok=True)

    def project_path(self, slug: str) -> Path:
        return self.workspace_root / slug

    def idea_path(self, slug: str) -> Path:
        return self.ideas_dir / f"{slug}.yaml"

    def backlog_path(self, slug: str) -> Path:
        return self.backlogs_dir / f"{slug}.yaml"

    def load_registry(self) -> dict:
        if not self.registry_file.exists():
            return {"projects": []}
        return json.loads(self.registry_file.read_text(encoding="utf-8"))

    def save_registry(self, data: dict) -> None:
        self.registry_file.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def register_project(self, slug: str, title: str) -> None:
        reg = self.load_registry()
        projects = reg.setdefault("projects", [])
        if not any(p.get("slug") == slug for p in projects):
            projects.append(
                {
                    "slug": slug,
                    "title": title,
                    "path": str(self.project_path(slug)),
                    "registered_at": utc_now().isoformat(),
                }
            )
            self.save_registry(reg)

    def save_idea(self, idea: ProjectIdea) -> Path:
        path = self.idea_path(idea.slug)
        data = idea.model_dump(mode="json")
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    def load_idea(self, slug: str) -> ProjectIdea | None:
        path = self.idea_path(slug)
        if not path.is_file():
            return None
        return ProjectIdea.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def list_ideas(self) -> list[ProjectIdea]:
        ideas: list[ProjectIdea] = []
        for path in sorted(self.ideas_dir.glob("*.yaml")):
            ideas.append(ProjectIdea.model_validate(yaml.safe_load(path.read_text(encoding="utf-8"))))
        return ideas

    def save_backlog(self, backlog: ProjectBacklog) -> Path:
        backlog.updated_at = utc_now()
        path = self.backlog_path(backlog.project_slug)
        data = backlog.model_dump(mode="json")
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    def load_backlog(self, slug: str) -> ProjectBacklog:
        path = self.backlog_path(slug)
        if path.is_file():
            return ProjectBacklog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        return ProjectBacklog(project_slug=slug)

    def list_backlogs(self) -> list[str]:
        return [p.stem for p in sorted(self.backlogs_dir.glob("*.yaml"))]
