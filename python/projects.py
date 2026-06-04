from __future__ import annotations

import shutil
from pathlib import Path

from python.config import ForgeConfig
from python.models import ProjectIdea, utc_now
from python.storage import ForgeStorage


class ProjectService:
    def __init__(self, forge: ForgeConfig, storage: ForgeStorage) -> None:
        self.forge = forge
        self.storage = storage

    def scaffold(self, idea: ProjectIdea, force: bool = False) -> Path:
        root = self.storage.project_path(idea.slug)
        if root.exists() and not force:
            raise FileExistsError(
                f"Project directory already exists: {root}. Use --force to overwrite metadata only."
            )
        root.mkdir(parents=True, exist_ok=True)

        template = self.forge.project_template
        dirs = template.get("directories", ["src", "tests", "docs", "scripts"])
        for name in dirs:
            (root / name).mkdir(parents=True, exist_ok=True)

        readme = _render_readme(idea, template.get("readme_intro", ""))
        (root / "README.md").write_text(readme, encoding="utf-8")

        forge_meta = root / ".python"
        forge_meta.mkdir(exist_ok=True)
        (forge_meta / "project.yaml").write_text(
            _yaml_dump(
                {
                    "slug": idea.slug,
                    "title": idea.title,
                    "forged_at": utc_now().isoformat(),
                    "forge_version": "0.1.0",
                }
            ),
            encoding="utf-8",
        )

        gitignore = template.get(
            "gitignore",
            ".env\n__pycache__/\n*.pyc\n.venv/\nnode_modules/\n.python/local/\n",
        )
        gi_path = root / ".gitignore"
        if not gi_path.exists():
            gi_path.write_text(gitignore, encoding="utf-8")

        req = template.get("requirements")
        if req and not (root / "requirements.txt").exists():
            (root / "requirements.txt").write_text(req, encoding="utf-8")

        self.storage.register_project(idea.slug, idea.title)
        return root

    def link_forge_backlog(self, slug: str) -> Path:
        """Copy or symlink backlog into project docs."""
        project = self.storage.project_path(slug)
        docs = project / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        src = self.storage.backlog_path(slug)
        dest = docs / "BACKLOG.yaml"
        if src.is_file():
            shutil.copy2(src, dest)
        return dest


def _render_readme(idea: ProjectIdea, intro: str) -> str:
    lines = [
        f"# {idea.title}",
        "",
        intro or f"> {idea.summary}",
        "",
        "## Vision",
        "",
        idea.vision or idea.summary,
        "",
        "## Success criteria",
        "",
    ]
    for c in idea.success_criteria:
        lines.append(f"- {c}")
    lines.extend(["", "## Constraints", ""])
    for c in idea.constraints:
        lines.append(f"- {c}")
    lines.extend(
        [
            "",
            "## Tags",
            "",
            ", ".join(idea.tags) if idea.tags else "_none_",
            "",
            "---",
            "",
            "_Scaffolded by [AityUahn](https://github.com/HyperlinksSpace/AityUahn)._",
            "",
        ]
    )
    return "\n".join(lines)


def _yaml_dump(data: dict) -> str:
    import yaml

    return yaml.safe_dump(data, sort_keys=False)
