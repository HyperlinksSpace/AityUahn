from __future__ import annotations

import json
import re

from python.config import ForgeConfig
from python.models import CompletionRequest, Message, ProjectIdea, utc_now
from python.providers import get_provider
from python.storage import ForgeStorage, slugify

IDEA_SYSTEM = """You are a product architect for the HyperlinksSpace project lab.
Given a short prompt, produce a structured project idea as JSON only (no markdown fences).
Schema:
{
  "title": "string",
  "summary": "one paragraph",
  "vision": "2-4 sentences",
  "constraints": ["string", ...],
  "success_criteria": ["string", ...],
  "tags": ["string", ...]
}
Be concrete, scoped for a small team, and suitable for iterative AI-assisted development."""


class IdeaService:
    def __init__(self, forge: ForgeConfig, storage: ForgeStorage) -> None:
        self.forge = forge
        self.storage = storage

    async def generate(
        self,
        prompt: str,
        slug: str | None = None,
        provider_id: str | None = None,
    ) -> ProjectIdea:
        pid = provider_id or self.forge.resolve_provider_id("idea")
        provider = get_provider(self.forge, pid)
        request = CompletionRequest(
            messages=[Message(role="user", content=prompt)],
            system=IDEA_SYSTEM,
            temperature=0.5,
        )
        result = await provider.complete(request)
        parsed = _parse_idea_json(result.text)
        title = parsed.get("title") or prompt[:80]
        idea_slug = slug or slugify(title)
        idea = ProjectIdea(
            slug=idea_slug,
            title=title,
            summary=parsed.get("summary", ""),
            vision=parsed.get("vision", ""),
            constraints=parsed.get("constraints", []),
            success_criteria=parsed.get("success_criteria", []),
            tags=parsed.get("tags", []),
            updated_at=utc_now(),
            source_provider=provider.id,
        )
        self.storage.save_idea(idea)
        return idea

    def create_manual(self, idea: ProjectIdea) -> ProjectIdea:
        idea.updated_at = utc_now()
        self.storage.save_idea(idea)
        return idea


def _parse_idea_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"title": text[:80], "summary": text}
