from __future__ import annotations

import json
import re
import uuid

from python.config import ForgeConfig
from python.models import (
    BacklogTask,
    CompletionRequest,
    Message,
    ProjectBacklog,
    TaskStatus,
    utc_now,
)
from python.providers import get_provider
from python.storage import ForgeStorage

BACKLOG_SYSTEM = """You are a technical lead breaking a project into actionable tasks.
Return JSON only (no markdown fences):
{
  "tasks": [
    {
      "title": "string",
      "description": "string",
      "priority": 1-100,
      "labels": ["string"],
      "depends_on_titles": ["optional title refs"],
      "test_command": "optional shell command to verify"
    }
  ]
}
Keep 5-15 tasks, ordered logically, each independently completable."""


class BacklogService:
    def __init__(self, forge: ForgeConfig, storage: ForgeStorage) -> None:
        self.forge = forge
        self.storage = storage

    def get(self, slug: str) -> ProjectBacklog:
        return self.storage.load_backlog(slug)

    def add_task(
        self,
        slug: str,
        title: str,
        description: str = "",
        priority: int = 50,
        labels: list[str] | None = None,
    ) -> BacklogTask:
        backlog = self.get(slug)
        task = BacklogTask(
            id=_new_task_id(),
            title=title,
            description=description,
            priority=priority,
            labels=labels or [],
        )
        backlog.tasks.append(task)
        self.storage.save_backlog(backlog)
        return task

    def update_status(self, slug: str, task_id: str, status: TaskStatus) -> BacklogTask:
        backlog = self.get(slug)
        for task in backlog.tasks:
            if task.id == task_id:
                task.status = status
                task.updated_at = utc_now()
                if status == TaskStatus.DONE:
                    task.completed_at = utc_now()
                self.storage.save_backlog(backlog)
                return task
        raise KeyError(f"Task {task_id} not found in {slug}")

    async def generate_from_idea(
        self,
        slug: str,
        extra_context: str = "",
        provider_id: str | None = None,
    ) -> ProjectBacklog:
        idea = self.storage.load_idea(slug)
        if not idea:
            raise ValueError(f"No idea found for '{slug}'. Run `aityuahn idea` first.")

        pid = provider_id or self.forge.resolve_provider_id("backlog")
        provider = get_provider(self.forge, pid)
        prompt = (
            f"Project: {idea.title}\n"
            f"Summary: {idea.summary}\n"
            f"Vision: {idea.vision}\n"
            f"Constraints: {idea.constraints}\n"
            f"Success criteria: {idea.success_criteria}\n"
            f"{extra_context}"
        )
        request = CompletionRequest(
            messages=[Message(role="user", content=prompt)],
            system=BACKLOG_SYSTEM,
        )
        result = await provider.complete(request)
        parsed = _parse_tasks_json(result.text)
        backlog = self.get(slug)
        title_to_id: dict[str, str] = {t.title: t.id for t in backlog.tasks}

        for item in parsed.get("tasks", []):
            task = BacklogTask(
                id=_new_task_id(),
                title=item.get("title", "Untitled"),
                description=item.get("description", ""),
                priority=int(item.get("priority", 50)),
                labels=item.get("labels", []),
                test_command=item.get("test_command"),
            )
            backlog.tasks.append(task)
            title_to_id[task.title] = task.id

        for item in parsed.get("tasks", []):
            deps = item.get("depends_on_titles") or []
            title = item.get("title")
            task = next((t for t in backlog.tasks if t.title == title), None)
            if task:
                task.depends_on = [title_to_id[d] for d in deps if d in title_to_id]

        self.storage.save_backlog(backlog)
        return backlog

    def progress_report(self, slug: str) -> dict:
        backlog = self.get(slug)
        p = backlog.progress
        return {
            "project": slug,
            "progress": p,
            "tasks": [self._task_dict(t) for t in self._sorted_tasks(backlog)],
        }

    def _sorted_tasks(self, backlog: ProjectBacklog) -> list[BacklogTask]:
        return sorted(backlog.tasks, key=lambda x: (-x.priority, x.created_at))

    def _task_dict(self, task: BacklogTask) -> dict:
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority,
            "labels": task.labels,
            "depends_on": task.depends_on,
            "test_command": task.test_command,
        }


def _new_task_id() -> str:
    return f"T-{uuid.uuid4().hex[:8]}"


def _parse_tasks_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
