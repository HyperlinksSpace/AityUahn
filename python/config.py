from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(BaseModel):
    """One connectable AI backend."""

    id: str
    kind: str
    enabled: bool = True
    default: bool = False
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class ForgeConfig(BaseModel):
    """Loaded from forge.yaml."""

    workspace_root: Path = Path(".")
    forge_data_dir: Path = Path(".python")
    default_provider: str = "claude"
    idea_provider: str | None = None
    backlog_provider: str | None = None
    task_provider: str | None = None
    providers: list[ProviderConfig] = Field(default_factory=list)
    project_template: dict[str, Any] = Field(default_factory=dict)
    test_defaults: dict[str, Any] = Field(default_factory=dict)

    def resolve_provider_id(self, role: str | None = None) -> str:
        if role == "idea" and self.idea_provider:
            return self.idea_provider
        if role == "backlog" and self.backlog_provider:
            return self.backlog_provider
        if role == "task" and self.task_provider:
            return self.task_provider
        return self.default_provider

    def get_provider(self, provider_id: str | None = None) -> ProviderConfig:
        pid = provider_id or self.default_provider
        for p in self.providers:
            if p.id == pid and p.enabled:
                return p
        enabled = [p for p in self.providers if p.enabled]
        if not enabled:
            raise ValueError("No enabled providers in forge.yaml")
        default = next((p for p in enabled if p.default), enabled[0])
        if provider_id:
            raise ValueError(f"Provider '{provider_id}' not found or disabled")
        return default


class EnvSettings(BaseSettings):
    """Environment overrides for paths and secrets."""

    model_config = SettingsConfigDict(
        env_prefix="PYTHON_",
        env_file=".env",
        extra="ignore",
    )

    workspace_root: Path | None = None
    forge_config: Path | None = None
    forge_data_dir: Path | None = None


def find_forge_config(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    candidates = [
        cwd / "forge.yaml",
        cwd / "config" / "forge.yaml",
        Path(__file__).resolve().parent.parent / "config" / "forge.example.yaml",
    ]
    env_path = os.environ.get("PYTHON_CONFIG")
    if env_path:
        return Path(env_path)
    for path in candidates:
        if path.is_file() and path.name != "forge.example.yaml":
            return path
    example = candidates[-1]
    if example.is_file():
        return example
    raise FileNotFoundError(
        "No forge.yaml found. Copy config/forge.example.yaml to forge.yaml and edit."
    )


def load_forge_config(config_path: Path | None = None) -> ForgeConfig:
    env = EnvSettings()
    path = config_path or env.forge_config or find_forge_config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if env.workspace_root:
        raw["workspace_root"] = str(env.workspace_root)
    if env.forge_data_dir:
        raw["forge_data_dir"] = str(env.forge_data_dir)

    cfg = ForgeConfig.model_validate(raw)
    cfg.workspace_root = Path(cfg.workspace_root).expanduser().resolve()
    cfg.forge_data_dir = Path(cfg.forge_data_dir).expanduser().resolve()
    if not cfg.forge_data_dir.is_absolute():
        cfg.forge_data_dir = (path.parent / cfg.forge_data_dir).resolve()
    return cfg


def resolve_api_key(provider: ProviderConfig) -> str | None:
    if provider.api_key:
        return provider.api_key
    if provider.api_key_env:
        return os.environ.get(provider.api_key_env)
    return None
