from __future__ import annotations

import httpx

from python.models import CompletionRequest, CompletionResult
from python.providers.base import BaseProvider

DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAICompatProvider(BaseProvider):
    """OpenAI-compatible chat completions (OpenAI, Ollama, vLLM, LiteLLM, etc.)."""

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        base = (self.config.base_url or DEFAULT_BASE).rstrip("/")
        model = self.config.model or "gpt-4o-mini"
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)

        headers = {"Content-Type": "application/json", **self.config.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{base}/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        return CompletionResult(text=text, provider=self.id, model=model, raw=data)
