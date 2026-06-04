from __future__ import annotations

import httpx

from python.models import CompletionRequest, CompletionResult, Message
from python.providers.base import BaseProvider

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_VERSION = "2023-06-01"


class ClaudeProvider(BaseProvider):
    """Anthropic Messages API — https://platform.claude.com/docs/en/api/overview"""

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        if not self.api_key:
            raise ValueError(
                f"API key missing for provider '{self.id}'. Set {self.config.api_key_env or 'api_key'}."
            )

        model = self.config.model or "claude-sonnet-4-20250514"
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        body: dict = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if request.system:
            body["system"] = request.system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.config.options.get("anthropic_version", DEFAULT_VERSION),
            "content-type": "application/json",
            **self.config.extra_headers,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(ANTHROPIC_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text_blocks = [
            b.get("text", "")
            for b in data.get("content", [])
            if b.get("type") == "text"
        ]
        return CompletionResult(
            text="\n".join(text_blocks).strip(),
            provider=self.id,
            model=model,
            raw=data,
        )

    @staticmethod
    def messages_from_prompt(prompt: str, system: str | None = None) -> CompletionRequest:
        return CompletionRequest(
            messages=[Message(role="user", content=prompt)],
            system=system,
        )
