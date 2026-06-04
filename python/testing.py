from __future__ import annotations

import asyncio
import subprocess
import uuid
from pathlib import Path

from python.config import ForgeConfig
from python.models import ProjectBacklog, TestRun, TestStatus, utc_now
from python.storage import ForgeStorage


class TestService:
    def __init__(self, forge: ForgeConfig, storage: ForgeStorage) -> None:
        self.forge = forge
        self.storage = storage

    def default_command(self, slug: str) -> str | None:
        defaults = self.forge.test_defaults
        per_project = defaults.get("projects", {}).get(slug)
        if per_project:
            return per_project
        project = self.storage.project_path(slug)
        if (project / "pyproject.toml").is_file():
            return defaults.get("python", "pytest -q")
        if (project / "package.json").is_file():
            return defaults.get("node", "npm test")
        return defaults.get("fallback")

    async def run(
        self,
        slug: str,
        command: str | None = None,
        cwd: Path | None = None,
    ) -> TestRun:
        cmd = command or self.default_command(slug)
        if not cmd:
            raise ValueError(f"No test command for project '{slug}'. Pass --command.")

        project_dir = cwd or self.storage.project_path(slug)
        run = TestRun(
            id=f"R-{uuid.uuid4().hex[:8]}",
            command=cmd,
            status=TestStatus.RUNNING,
            started_at=utc_now(),
        )
        backlog = self.storage.load_backlog(slug)
        backlog.test_runs.append(run)
        self.storage.save_backlog(backlog)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = (stdout or b"").decode(errors="replace")
        run.finished_at = utc_now()
        run.exit_code = proc.returncode
        run.output_tail = output[-8000:]
        run.status = TestStatus.PASSED if proc.returncode == 0 else TestStatus.FAILED

        backlog = self.storage.load_backlog(slug)
        backlog.test_runs[-1] = run
        self.storage.save_backlog(backlog)
        return run

    def run_sync(self, slug: str, command: str | None = None, cwd: Path | None = None) -> TestRun:
        return asyncio.run(self.run(slug, command, cwd))

    def summary(self, slug: str) -> dict:
        backlog: ProjectBacklog = self.storage.load_backlog(slug)
        runs = backlog.test_runs[-10:]
        return {
            "project": slug,
            "last_runs": [
                {
                    "id": r.id,
                    "command": r.command,
                    "status": r.status.value,
                    "exit_code": r.exit_code,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in runs
            ],
        }


def run_command_blocking(command: str, cwd: Path, timeout: int = 600) -> tuple[int, str]:
    result = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output
