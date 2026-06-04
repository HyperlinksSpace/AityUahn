from __future__ import annotations

import base64
import json

import httpx

from python.models import CompletionRequest, CompletionResult, Message
from python.providers.base import BaseProvider

# Cloud Agents API — https://cursor.com/docs/api
DEFAULT_BASE = "https://api.cursor.com"


class CursorProvider(BaseProvider):
    """
    Uses Cursor HTTP API for agent-style work.
    For full local/cloud agent runs, prefer the Cursor SDK (`cursor-sdk` / `@cursor/sdk`).
    This provider posts a prompt via the agents API pattern configured in forge.yaml.
    """

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        if not self.api_key:
            raise ValueError(
                f"API key missing for provider '{self.id}'. Set {self.config.api_key_env or 'CURSOR_API_KEY'}."
            )

        base = (self.config.base_url or DEFAULT_BASE).rstrip("/")
        mode = self.config.options.get("mode", "messages")

        if mode == "sdk_note":
            return CompletionResult(
                text=(
                    "Cursor SDK mode: install `cursor-sdk` and run scripts/run_cursor_agent.py "
                    "or set provider options.mode to 'http' with a completion endpoint."
                ),
                provider=self.id,
                model=self.config.model or "composer-2.5",
            )

        # Lightweight completion via /v1/chat/completions-style proxy if configured
        completion_path = self.config.options.get("completion_path")
        if completion_path:
            return await self._http_completion(base, completion_path, request)

        # Default: use a simple prompt relay endpoint or agent launch stub
        agent_path = self.config.options.get("agent_path", "/v0/agents")
        prompt = self._flatten_messages(request)
        body = {
            "prompt": {"text": prompt},
            "model": self.config.model or "composer-2.5",
            **self.config.options.get("agent_body", {}),
        }
        headers = self._auth_headers()

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{base}{agent_path}", json=body, headers=headers)
            if resp.status_code == 404 and mode != "agent":
                return await self._fallback_messages_api(base, request)
            resp.raise_for_status()
            data = resp.json()

        text = (
            data.get("result")
            or data.get("output")
            or data.get("message")
            or json.dumps(data, indent=2)
        )
        if isinstance(text, dict):
            text = json.dumps(text, indent=2)
        return CompletionResult(
            text=str(text),
            provider=self.id,
            model=self.config.model or "composer-2.5",
            raw=data if isinstance(data, dict) else None,
        )

    async def _fallback_messages_api(self, base: str, request: CompletionRequest) -> CompletionResult:
        """Some teams expose an OpenAI-compatible gateway in front of Cursor."""
        return await self._http_completion(
            base,
            self.config.options.get("fallback_path", "/v1/chat/completions"),
            request,
        )

    async def _http_completion(
        self, base: str, path: str, request: CompletionRequest
    ) -> CompletionResult:
        model = self.config.model or "composer-2.5"
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{base}{path}",
                json=body,
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            or data.get("text", "")
        )
        return CompletionResult(text=text, provider=self.id, model=model, raw=data)

    def _auth_headers(self) -> dict[str, str]:
        token = self.api_key or ""
        if self.config.options.get("auth", "bearer") == "basic":
            encoded = base64.b64encode(f"{token}:".encode()).decode()
            auth = f"Basic {encoded}"
        else:
            auth = f"Bearer {token}"
        return {
            "Authorization": auth,
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }

    @staticmethod
    def _flatten_messages(request: CompletionRequest) -> str:
        parts = []
        if request.system:
            parts.append(f"[system]\n{request.system}")
        for m in request.messages:
            parts.append(f"[{m.role}]\n{m.content}")
        return "\n\n".join(parts)
