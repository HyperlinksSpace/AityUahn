from __future__ import annotations

from pathlib import Path

from python.backlog import BacklogService
from python.config import ForgeConfig, load_forge_config
from python.ideas import IdeaService
from python.models import CompletionRequest, Message, ProjectIdea, TaskStatus
from python.projects import ProjectService
from python.providers import get_provider
from python.storage import ForgeStorage
from python.testing import TestService


class LForge:
    """Main orchestrator for local and cloud forge operations."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config = load_forge_config(config_path)
        self.storage = ForgeStorage(
            self.config.forge_data_dir,
            self.config.workspace_root,
        )
        self.ideas = IdeaService(self.config, self.storage)
        self.backlog = BacklogService(self.config, self.storage)
        self.projects = ProjectService(self.config, self.storage)
        self.testing = TestService(self.config, self.storage)

    async def complete_prompt(
        self,
        prompt: str,
        system: str | None = None,
        provider_id: str | None = None,
    ) -> str:
        provider = get_provider(self.config, provider_id)
        result = await provider.complete(
            CompletionRequest(
                messages=[Message(role="user", content=prompt)],
                system=system,
            )
        )
        return result.text

    async def forge_project(
        self,
        prompt: str,
        slug: str | None = None,
        scaffold: bool = True,
        generate_backlog: bool = True,
    ) -> dict:
        idea = await self.ideas.generate(prompt, slug=slug)
        result = {"idea": idea.model_dump(mode="json")}
        if generate_backlog:
            bl = await self.backlog.generate_from_idea(idea.slug)
            result["backlog"] = self.backlog.progress_report(idea.slug)
            result["task_count"] = len(bl.tasks)
        if scaffold:
            path = self.projects.scaffold(idea)
            self.projects.link_forge_backlog(idea.slug)
            result["project_path"] = str(path)
        return result

    def list_all(self) -> dict:
        reg = self.storage.load_registry()
        return {
            "workspace": str(self.config.workspace_root),
            "forge_data": str(self.config.forge_data_dir),
            "ideas": [i.slug for i in self.storage.list_ideas()],
            "backlogs": self.storage.list_backlogs(),
            "registry": reg.get("projects", []),
        }
