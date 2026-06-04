from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from python.forge import LForge
from python.models import ProjectIdea, TaskStatus

console = Console()


def _run(coro):
    return asyncio.run(coro)


@click.group()
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """lForge — ideate, backlog, scaffold, and develop projects with pluggable AI."""
    ctx.ensure_object(dict)
    ctx.obj["forge"] = LForge(config_path)


@main.command("init")
@click.option("--workspace", type=click.Path(path_type=Path), default=None)
@click.pass_context
def init_cmd(ctx: click.Context, workspace: Path | None) -> None:
    """Initialize forge data directory and print paths."""
    forge: LForge = ctx.obj["forge"]
    if workspace:
        forge.config.workspace_root = workspace.resolve()
    forge.storage.forge_data_dir.mkdir(parents=True, exist_ok=True)
    console.print("[green]lForge ready[/green]")
    console.print(f"  Workspace:   {forge.config.workspace_root}")
    console.print(f"  Forge data:  {forge.config.forge_data_dir}")
    console.print(f"  Providers:   {[p.id for p in forge.config.providers if p.enabled]}")


@main.command("list")
@click.pass_context
def list_cmd(ctx: click.Context) -> None:
    """List ideas, backlogs, and registered projects."""
    forge: LForge = ctx.obj["forge"]
    data = forge.list_all()
    table = Table(title="lForge registry")
    table.add_column("Type")
    table.add_column("Items")
    table.add_row("Workspace", data["workspace"])
    table.add_row("Ideas", ", ".join(data["ideas"]) or "—")
    table.add_row("Backlogs", ", ".join(data["backlogs"]) or "—")
    projects = ", ".join(p["slug"] for p in data["registry"]) or "—"
    table.add_row("Projects", projects)
    console.print(table)


@main.command("idea")
@click.argument("prompt")
@click.option("--slug", default=None, help="Project slug (folder name).")
@click.option("--provider", default=None, help="Provider id from forge.yaml.")
@click.option("--json-out", is_flag=True, help="Print raw JSON.")
@click.pass_context
def idea_cmd(
    ctx: click.Context,
    prompt: str,
    slug: str | None,
    provider: str | None,
    json_out: bool,
) -> None:
    """Generate a structured project idea from a prompt."""
    forge: LForge = ctx.obj["forge"]
    idea = _run(forge.ideas.generate(prompt, slug=slug, provider_id=provider))
    if json_out:
        console.print_json(json.dumps(idea.model_dump(mode="json"), default=str))
        return
    console.print(f"[bold]{idea.title}[/bold] ({idea.slug})")
    console.print(idea.summary)
    console.print(f"Saved: {forge.storage.idea_path(idea.slug)}")


@main.command("backlog")
@click.argument("slug")
@click.option("--generate", is_flag=True, help="AI-generate tasks from the idea.")
@click.option("--provider", default=None)
@click.option("--context", default="", help="Extra context for generation.")
@click.pass_context
def backlog_cmd(
    ctx: click.Context,
    slug: str,
    generate: bool,
    provider: str | None,
    context: str,
) -> None:
    """Show or generate a project backlog."""
    forge: LForge = ctx.obj["forge"]
    if generate:
        _run(forge.backlog.generate_from_idea(slug, extra_context=context, provider_id=provider))
    report = forge.backlog.progress_report(slug)
    table = Table(title=f"Backlog: {slug} ({report['progress']['percent']}% done)")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Pri")
    table.add_column("Title")
    for t in report["tasks"]:
        table.add_row(t["id"], t["status"], str(t["priority"]), t["title"])
    console.print(table)


@main.command("task")
@click.argument("slug")
@click.argument("action", type=click.Choice(["add", "start", "done", "block"]))
@click.argument("title", required=False)
@click.option("--id", "task_id", default=None)
@click.pass_context
def task_cmd(
    ctx: click.Context,
    slug: str,
    action: str,
    title: str | None,
    task_id: str | None,
) -> None:
    """Add or update backlog tasks."""
    forge: LForge = ctx.obj["forge"]
    if action == "add":
        if not title:
            raise click.UsageError("TITLE required for add")
        task = forge.backlog.add_task(slug, title)
        console.print(f"Added {task.id}: {task.title}")
        return
    if not task_id:
        raise click.UsageError("--id required for start|done|block")
    status_map = {
        "start": TaskStatus.IN_PROGRESS,
        "done": TaskStatus.DONE,
        "block": TaskStatus.BLOCKED,
    }
    task = forge.backlog.update_status(slug, task_id, status_map[action])
    console.print(f"Updated {task.id} → {task.status.value}")


@main.command("scaffold")
@click.argument("slug")
@click.option("--force", is_flag=True)
@click.pass_context
def scaffold_cmd(ctx: click.Context, slug: str, force: bool) -> None:
    """Create project folder from a saved idea."""
    forge: LForge = ctx.obj["forge"]
    idea = forge.storage.load_idea(slug)
    if not idea:
        raise click.ClickException(f"No idea for '{slug}'. Run `aityuahn idea` first.")
    path = forge.projects.scaffold(idea, force=force)
    forge.projects.link_forge_backlog(slug)
    console.print(f"[green]Scaffolded[/green] {path}")


@main.command("forge")
@click.argument("prompt")
@click.option("--slug", default=None)
@click.option("--no-scaffold", is_flag=True)
@click.option("--no-backlog", is_flag=True)
@click.pass_context
def forge_cmd(
    ctx: click.Context,
    prompt: str,
    slug: str | None,
    no_scaffold: bool,
    no_backlog: bool,
) -> None:
    """Full pipeline: idea → backlog → scaffold."""
    forge: LForge = ctx.obj["forge"]
    result = _run(
        forge.forge_project(
            prompt,
            slug=slug,
            scaffold=not no_scaffold,
            generate_backlog=not no_backlog,
        )
    )
    console.print_json(json.dumps(result, default=str))


@main.command("test")
@click.argument("slug")
@click.option("--command", default=None)
@click.pass_context
def test_cmd(ctx: click.Context, slug: str, command: str | None) -> None:
    """Run tests for a forged project and record results."""
    forge: LForge = ctx.obj["forge"]
    run = _run(forge.testing.run(slug, command=command))
    color = "green" if run.status.value == "passed" else "red"
    console.print(f"[{color}]{run.status.value.upper()}[/{color}] exit={run.exit_code}")
    if run.output_tail:
        console.print(run.output_tail[-2000:])


@main.command("prompt")
@click.argument("text")
@click.option("--provider", default=None)
@click.option("--system", default=None)
@click.pass_context
def prompt_cmd(ctx: click.Context, text: str, provider: str | None, system: str | None) -> None:
    """Send a one-off prompt to the configured AI provider."""
    forge: LForge = ctx.obj["forge"]
    out = _run(forge.complete_prompt(text, system=system, provider_id=provider))
    console.print(out)


@main.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8765, type=int, help="Bind port.")
@click.pass_context
def serve_cmd(ctx: click.Context, host: str, port: int) -> None:
    """Run HTTP API + test UI (backend for .python data)."""
    import uvicorn

    from python.backend.app import create_app

    forge: LForge = ctx.obj["forge"]
    app = create_app(forge)
    console.print(f"[green]AityUahn UI[/green]  http://{host}:{port}/")
    console.print(f"[dim]API docs[/dim]     http://{host}:{port}/docs")
    console.print(f"[dim]forge data[/dim]  {forge.config.forge_data_dir}")
    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command("providers")
@click.pass_context
def providers_cmd(ctx: click.Context) -> None:
    """List configured AI providers."""
    forge: LForge = ctx.obj["forge"]
    table = Table(title="Providers")
    table.add_column("ID")
    table.add_column("Kind")
    table.add_column("Model")
    table.add_column("Default")
    table.add_column("Enabled")
    for p in forge.config.providers:
        table.add_row(
            p.id,
            p.kind,
            p.model or "—",
            "yes" if p.default else "",
            "yes" if p.enabled else "no",
        )
    console.print(table)


if __name__ == "__main__":
    main()
