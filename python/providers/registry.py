from __future__ import annotations

from python.config import ProviderConfig
from python.providers.base import BaseProvider
from python.providers.claude import ClaudeProvider
from python.providers.cursor import CursorProvider
from python.providers.http_custom import HttpProvider
from python.providers.openai_compat import OpenAICompatProvider


def build_provider(config: ProviderConfig) -> BaseProvider:
    kind = config.kind.lower()
    if kind == "claude":
        return ClaudeProvider(config)
    if kind == "cursor":
        return CursorProvider(config)
    if kind in ("openai_compat", "openai", "openai-compatible"):
        return OpenAICompatProvider(config)
    if kind in ("http", "custom", "tinymodel"):
        return HttpProvider(config)
    raise ValueError(f"Unknown provider kind: {config.kind}")
