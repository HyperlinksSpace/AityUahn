from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from python.forge import LForge
from python.models import TaskStatus

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
@click.option("--demo", is_flag=True, help="Seed sample dashboard data when forge data is empty.")
@click.option(
    "--with-saas",
    is_flag=True,
    help="Also run SaaS API on this port (dev monolith). Production SaaS is deployed separately.",
)
@click.option("--open", "open_browser", is_flag=True, help="Open controller in browser after start.")
@click.pass_context
def serve_cmd(ctx: click.Context, host: str, port: int, demo: bool, with_saas: bool, open_browser: bool) -> None:
    """Run local forge API + UI (ideas, backlog, scaffold, agents)."""
    import uvicorn

    from python.backend.app import create_app
    from python.demo import seed_demo_data

    forge: LForge = ctx.obj["forge"]
    if demo or not forge.storage.list_backlogs():
        slug = seed_demo_data(forge.storage)
        if demo or slug:
            console.print(f"[dim]Demo data[/dim]     {slug} (see dashboard)")
    app = create_app(forge, include_saas=with_saas)
    console.print(f"[green]Forge UI[/green]    http://{host}:{port}/")
    console.print(f"[dim]Controller[/dim]  http://{host}:{port}/controller.html")
    console.print(f"[dim]Guide[/dim]       http://{host}:{port}/guide.html")
    console.print(f"[dim]Forge API[/dim]    http://{host}:{port}/api/health")
    console.print(f"[dim]Open UI[/dim]       aityuahn open")
    if with_saas:
        console.print(f"[dim]SaaS API[/dim]     http://{host}:{port}/api/saas/pricing")
    else:
        console.print("[dim]SaaS[/dim]         off — set defaultSaasApi in UI config for cloud auth")
    console.print(f"[dim]forge data[/dim]  {forge.config.forge_data_dir}")
    if open_browser:
        import threading
        import time
        import webbrowser

        url = f"http://{host}:{port}/controller.html"

        def _open() -> None:
            time.sleep(0.8)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()
        console.print(f"[dim]Browser[/dim]      opening {url}")
    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command("serve-saas")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8780, type=int, help="Bind port.")
@click.pass_context
def serve_saas_cmd(ctx: click.Context, host: str, port: int) -> None:
    """Run cloud SaaS API only (auth, teams, billing) — for Vercel/Neon dev."""
    import uvicorn

    from python.backend.saas_app import create_saas_app

    forge: LForge = ctx.obj["forge"]
    app = create_saas_app(forge)
    console.print(f"[green]SaaS API[/green]     http://{host}:{port}/api/saas/pricing")
    console.print(f"[dim]health[/dim]       http://{host}:{port}/api/health")
    console.print("[dim]store[/dim]        JSON files until Neon is wired")
    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command("ping")
@click.option("--forge-url", default="http://127.0.0.1:8765", show_default=True, help="Local forge API base URL.")
@click.option("--quiet", "-q", is_flag=True, help="Print one line only (for scripts).")
def ping_cmd(forge_url: str, quiet: bool) -> None:
    """Quick health check — one line, exit 0 when forge is up."""
    import httpx

    url = forge_url.rstrip("/") + "/api/health"
    try:
        r = httpx.get(url, headers={"Accept": "application/json"}, timeout=5.0)
        r.raise_for_status()
        body = r.json()
    except httpx.HTTPError as exc:
        if quiet:
            console.print(f"fail {forge_url} ({exc})")
        else:
            console.print(f"[red]Forge unreachable[/red] at {url}: {exc}")
        raise SystemExit(1) from exc

    ok = body.get("ok") is True and body.get("role") == "forge"
    version = body.get("version", "?")
    uptime = body.get("uptime_seconds")
    up = f" uptime={uptime}s" if uptime is not None else ""
    line = f"ok forge v{version}{up}" if ok else f"fail forge ({body.get('role', 'unknown')})"
    if quiet:
        console.print(line)
    elif ok:
        console.print(f"[green]{line}[/green]")
    else:
        console.print(f"[red]{line}[/red]")
    if not ok:
        raise SystemExit(1)


@main.command("dashboard")
@click.option("--forge-url", default="http://127.0.0.1:8765", show_default=True, help="Local forge API base URL.")
@click.option("--json-out", is_flag=True, help="Print raw JSON.")
def dashboard_cmd(forge_url: str, json_out: bool) -> None:
    """Print kanban summary from a running forge API."""
    import httpx

    url = forge_url.rstrip("/") + "/api/dashboard"
    try:
        r = httpx.get(url, headers={"Accept": "application/json"}, timeout=8.0)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError as exc:
        console.print(f"[red]Could not fetch {url}[/red]: {exc}")
        console.print("[dim]Start the forge:[/dim] aityuahn serve --demo")
        raise SystemExit(1) from exc

    if json_out:
        console.print_json(json.dumps(data, default=str))
        return

    summary = data.get("summary") or {}
    console.print(
        f"[bold]Dashboard[/bold] — {summary.get('projects', 0)} projects, "
        f"{summary.get('done', 0)}/{summary.get('tasks', 0)} tasks done "
        f"({summary.get('percent', 0)}%)"
    )
    projects = data.get("projects") or []
    if not projects:
        console.print("[dim]No projects yet — try aityuahn serve --demo[/dim]")
        return
    table = Table(title="Projects")
    table.add_column("Slug")
    table.add_column("Name")
    table.add_column("Progress")
    table.add_column("In progress")
    for p in projects:
        prog = p.get("progress") or {}
        table.add_row(
            p.get("slug", "—"),
            p.get("name", "—"),
            f"{prog.get('done', 0)}/{prog.get('total', 0)} ({prog.get('percent', 0)}%)",
            str(prog.get("in_progress", 0)),
        )
    console.print(table)


@main.command("info")
@click.option("--forge-url", default="http://127.0.0.1:8765", show_default=True, help="Forge or SaaS API base URL.")
@click.option("--json-out", is_flag=True, help="Print raw JSON.")
def info_cmd(forge_url: str, json_out: bool) -> None:
    """Fetch /api/info from a running forge or SaaS API."""
    import httpx

    url = forge_url.rstrip("/") + "/api/info"
    try:
        r = httpx.get(url, headers={"Accept": "application/json"}, timeout=8.0)
        r.raise_for_status()
        body = r.json()
    except httpx.HTTPError as exc:
        console.print(f"[red]Could not fetch {url}[/red]: {exc}")
        raise SystemExit(1) from exc

    if json_out:
        console.print_json(json.dumps(body, default=str))
        return

    table = Table(title=f"{body.get('name', 'API')} · {body.get('version', '?')}")
    table.add_column("Field")
    table.add_column("Value")
    for key in ("role", "version", "workspace", "forge_data", "default_provider", "storage", "serverless"):
        if key in body and body[key] is not None:
            table.add_row(key, str(body[key]))
    if body.get("providers_enabled"):
        table.add_row("providers_enabled", ", ".join(body["providers_enabled"]))
    console.print(table)
    links = body.get("links") or {}
    if links:
        console.print("[bold]Links[/bold]")
        for name, path in links.items():
            console.print(f"  {name}: {forge_url.rstrip('/')}{path}")


@main.command("status")
@click.option("--forge-url", default="http://127.0.0.1:8765", show_default=True, help="Local forge API base URL.")
@click.option("--saas-url", default=None, help="Cloud SaaS API base URL (optional).")
@click.option("--json-out", is_flag=True, help="Print raw JSON.")
@click.pass_context
def status_cmd(ctx: click.Context, forge_url: str, saas_url: str | None, json_out: bool) -> None:
    """Show local forge config and whether APIs are reachable."""
    from python.status_report import build_status_report

    forge: LForge = ctx.obj["forge"]
    report = build_status_report(forge, forge_url, saas_url)
    if json_out:
        console.print_json(json.dumps(report.to_dict(), default=str))
        return

    table = Table(title=f"AityUahn status · {report.version}")
    table.add_column("Item")
    table.add_column("Value")
    for row in report.rows:
        if row.live is True:
            mark = "[green]●[/green] "
        elif row.live is False:
            mark = "[red]●[/red] "
        else:
            mark = ""
        table.add_row(row.key, f"{mark}{row.value}")
    console.print(table)
    if report.forge_reachable:
        console.print("[green]Forge is live[/green] — run [bold]aityuahn open[/bold] or connect in the controller")
    else:
        console.print("[yellow]Forge offline[/yellow] — run [bold]aityuahn serve --demo[/bold]")


@main.command("version")
def version_cmd() -> None:
    """Print installed package version."""
    from python.saas.health import app_version

    console.print(f"aityuahn {app_version()}")


@main.command("doctor")
@click.option("--forge-url", default="http://127.0.0.1:8765", show_default=True, help="Local forge API base URL.")
@click.option("--saas-url", default=None, help="Cloud SaaS API base URL (optional).")
@click.option("--json-out", is_flag=True, help="Print raw JSON.")
def doctor_cmd(forge_url: str, saas_url: str | None, json_out: bool) -> None:
    """Check local forge and optional cloud SaaS readiness (detailed table)."""
    from python.verify_setup import run_verification

    report = run_verification(forge_url, saas_url)
    payload: dict[str, object] = {
        "forge_url": report.forge_url,
        "saas_url": report.saas_url,
        "ok": report.ok,
        "checks": [
            {"name": c.name, "ok": c.ok, "detail": c.detail, **({"data": c.data} if c.data else {})}
            for c in report.checks
        ],
    }
    if json_out:
        console.print_json(json.dumps(payload, default=str))
    else:
        table = Table(title="AityUahn doctor")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        for check in report.checks:
            table.add_row(
                check.name,
                "[green]ok[/green]" if check.ok else "[red]fail[/red]",
                check.detail,
            )
        console.print(table)
        if report.ok:
            console.print("[green]All checks passed[/green]")
        else:
            console.print(f"[red]{report.failed_count} check(s) failed[/red]")
    if not report.ok:
        raise SystemExit(1)


@main.command("open")
@click.option(
    "--page",
    type=click.Choice(["controller", "guide", "docs", "landing"], case_sensitive=False),
    default="controller",
    show_default=True,
    help="UI page to open.",
)
@click.option("--host", default="127.0.0.1", help="Forge host (must be running).")
@click.option("--port", default=8765, type=int, help="Forge port.")
def open_cmd(page: str, host: str, port: int) -> None:
    """Open the forge UI in your default browser."""
    import webbrowser

    paths = {
        "controller": "/controller.html",
        "guide": "/guide.html",
        "docs": "/docs.html",
        "landing": "/",
    }
    url = f"http://{host}:{port}{paths[page]}"
    console.print(f"[green]Opening[/green] {url}")
    console.print("[dim]Start the forge first if needed:[/dim] aityuahn serve --demo")
    webbrowser.open(url)


@main.command("verify")
@click.option("--forge-url", default="http://127.0.0.1:8765", show_default=True, help="Local forge API base URL.")
@click.option("--saas-url", default=None, help="Cloud SaaS API base URL (optional).")
@click.option("--json-out", is_flag=True, help="Print raw JSON.")
def verify_cmd(forge_url: str, saas_url: str | None, json_out: bool) -> None:
    """Verify forge and optional cloud SaaS are reachable (pass/fail, for scripts and CI)."""
    from python.verify_setup import run_verification

    report = run_verification(forge_url, saas_url)
    payload = {
        "forge_url": report.forge_url,
        "saas_url": report.saas_url,
        "ok": report.ok,
        "checks": [
            {"name": c.name, "ok": c.ok, "detail": c.detail, **({"data": c.data} if c.data else {})}
            for c in report.checks
        ],
    }
    if json_out:
        console.print_json(json.dumps(payload, default=str))
    else:
        for check in report.checks:
            mark = "[green]✓[/green]" if check.ok else "[red]✗[/red]"
            console.print(f"{mark} {check.name:5}  {check.detail}")
        if report.ok:
            console.print("[green]Verification passed[/green]")
        else:
            console.print(f"[red]Verification failed ({report.failed_count} check(s))[/red]")
    if not report.ok:
        raise SystemExit(1)


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
