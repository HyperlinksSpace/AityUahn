from __future__ import annotations

from abc import ABC, abstractmethod

from python.config import ForgeConfig, ProviderConfig, resolve_api_key
from python.models import CompletionRequest, CompletionResult


class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.api_key = resolve_api_key(config)

    @property
    def id(self) -> str:
        return self.config.id

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResult:
        ...


def get_provider(forge: ForgeConfig, provider_id: str | None = None) -> BaseProvider:
    from python.providers.registry import build_provider

    cfg = forge.get_provider(provider_id)
    return build_provider(cfg)
