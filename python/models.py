from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    IDEA = "idea"
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProviderKind(str, Enum):
    CURSOR = "cursor"
    CLAUDE = "claude"
    OPENAI_COMPAT = "openai_compat"
    HTTP = "http"


class Message(BaseModel):
    role: str
    content: str


class CompletionRequest(BaseModel):
    messages: list[Message]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.4
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompletionResult(BaseModel):
    text: str
    provider: str
    model: str
    raw: dict[str, Any] | None = None


class ProjectIdea(BaseModel):
    slug: str
    title: str
    summary: str
    vision: str = ""
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    source_provider: str | None = None


class BacklogTask(BaseModel):
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.BACKLOG
    priority: int = 50
    labels: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    assignee: str | None = None
    test_command: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)


class TestRun(BaseModel):
    id: str
    command: str
    status: TestStatus = TestStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    output_tail: str = ""


class ProjectBacklog(BaseModel):
    project_slug: str
    tasks: list[BacklogTask] = Field(default_factory=list)
    test_runs: list[TestRun] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def progress(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for task in self.tasks:
            counts[task.status.value] = counts.get(task.status.value, 0) + 1
        total = len(self.tasks)
        done = counts.get(TaskStatus.DONE.value, 0)
        return {
            "total": total,
            "done": done,
            "percent": round(100 * done / total, 1) if total else 0.0,
            **counts,
        }
