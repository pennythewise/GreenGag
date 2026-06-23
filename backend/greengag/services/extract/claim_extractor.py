"""Claude-based ESG claim extraction with Pydantic validation + 1 retry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from greengag.config import settings
from greengag.models.extraction import ExtractionResponse, RetrievedChunk

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "esg_claim_extraction.md"


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"--- CHUNK {i} (page {c.page}, pillar_hint={c.pillar_hint}) ---\n"
            f"Section: {c.section_heading or 'N/A'}\n"
            f"{c.content}\n"
        )
    return "\n".join(parts)


class ClaimExtractor:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for extraction.")
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_extraction_model
        self.system_prompt = _load_system_prompt()

    async def extract(
        self,
        *,
        filename: str,
        chunks: list[RetrievedChunk],
        pillar_status: dict,
    ) -> ExtractionResponse:
        user_content = (
            f"Document filename: {filename}\n\n"
            f"Pillar retrieval status:\n{json.dumps(pillar_status, indent=2)}\n\n"
            f"Retrieved report excerpts ({len(chunks)} chunks):\n\n"
            f"{_format_chunks(chunks)}\n\n"
            "Extract all verifiable ESG claims from the excerpts above. "
            "Return ONLY valid JSON matching the schema in the system prompt."
        )

        last_error: str | None = None
        for attempt in range(2):
            messages = [{"role": "user", "content": user_content}]
            if attempt == 1 and last_error:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response failed validation: {last_error}. "
                            "Fix the JSON and return ONLY valid JSON."
                        ),
                    }
                )

            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                messages=messages,
            )
            raw = "".join(
                block.text for block in resp.content if hasattr(block, "text")
            )
            try:
                payload = json.loads(_strip_json_fence(raw))
                return ExtractionResponse.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)

        raise ValueError(f"Extraction failed after retry: {last_error}")
