from __future__ import annotations

import httpx

from python.models import CompletionRequest, CompletionResult
from python.providers.base import BaseProvider


class HttpProvider(BaseProvider):
    """
    Generic HTTP provider for custom stacks (e.g. TinyModel Gradio API, local inference).
    Configure base_url + options.request_template in forge.yaml.
    """

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        base = (self.config.base_url or "").rstrip("/")
        path = self.config.options.get("path", "/v1/chat/completions")
        method = self.config.options.get("method", "POST").upper()

        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)

        body = self.config.options.get("body_template") or {
            "model": self.config.model or "default",
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if "{prompt}" in str(body):
            prompt = "\n".join(m.content for m in request.messages)
            body = {"prompt": prompt, "model": self.config.model}

        headers = {"Content-Type": "application/json", **self.config.extra_headers}
        if self.api_key:
            header_name = self.config.options.get("api_key_header", "Authorization")
            prefix = self.config.options.get("api_key_prefix", "Bearer ")
            headers[header_name] = f"{prefix}{self.api_key}".strip()

        response_path = self.config.options.get("response_json_path", "choices.0.message.content")

        async with httpx.AsyncClient(timeout=120.0) as client:
            url = f"{base}{path}" if base else path
            resp = await client.request(method, url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}

        text = _extract_path(data, response_path) or data.get("text") or str(data)
        return CompletionResult(
            text=str(text),
            provider=self.id,
            model=self.config.model or "custom",
            raw=data if isinstance(data, dict) else None,
        )


def _extract_path(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur
