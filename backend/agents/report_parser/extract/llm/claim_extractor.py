"""OpenAI-based ESG claim extraction with Pydantic validation + 1 retry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import ValidationError

from ..llm.models import ClaimCandidate, ExtractionResponse, RetrievedChunk
from ..rag.pillar_queries import PILLARS
from config import settings
from models.schemas import EsgPillar

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "esg_claim_extraction.md"


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


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


def _format_candidates(candidates: list[ClaimCandidate]) -> str:
    parts: list[str] = []
    for candidate in candidates:
        parts.append(
            f"--- CANDIDATE {candidate.id} ---\n"
            f"pillar: {candidate.pillar}\n"
            f"page: {candidate.page}\n"
            f"section: {candidate.section_heading or 'N/A'}\n"
            f"routing_score: {candidate.routing_score:.4f}\n"
            f"raw_text: {candidate.raw_text}\n"
        )
    return "\n".join(parts)


class ClaimExtractor:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for extraction.")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_extraction_model
        self.system_prompt = _load_system_prompt()

    async def extract_for_pillar(
        self,
        *,
        filename: str,
        pillar: EsgPillar,
        chunks: list[RetrievedChunk],
        pillar_status: dict,
    ) -> ExtractionResponse:
        user_content = (
            f"Document filename: {filename}\n\n"
            f"Extract ONLY **{pillar}** pillar claims from the excerpts below.\n"
            f"Set `pillar` to \"{pillar}\" for every claim unless the text clearly "
            f"belongs to another pillar with stronger evidence.\n\n"
            f"Pillar retrieval status:\n{json.dumps(pillar_status, indent=2)}\n\n"
            f"Retrieved report excerpts ({len(chunks)} chunks, routed to {pillar}):\n\n"
            f"{_format_chunks(chunks)}\n\n"
            "Extract all verifiable measurable ESG claims from the excerpts above. "
            "Return ONLY valid JSON matching the schema in the system prompt."
        )

        return await self._call_llm(user_content)

    async def normalize_candidates_for_pillar(
        self,
        *,
        filename: str,
        pillar: EsgPillar,
        candidates: list[ClaimCandidate],
    ) -> ExtractionResponse:
        user_content = (
            f"Document filename: {filename}\n\n"
            f"The deterministic NLP layer found {len(candidates)} measurable "
            f"{pillar} claim candidate(s). Normalize these candidates only.\n"
            "Return exactly one claim object per candidate. Do not add claims that "
            "are not listed. Preserve each candidate `id` and `raw_text` exactly.\n\n"
            f"{_format_candidates(candidates)}\n\n"
            "Return ONLY valid JSON matching the schema in the system prompt."
        )

        return await self._call_llm(user_content)

    async def extract_all_pillars(
        self,
        *,
        filename: str,
        pillar_chunks: dict[EsgPillar, list[RetrievedChunk]],
        pillar_status: dict[EsgPillar, dict],
    ) -> ExtractionResponse:
        merged = ExtractionResponse()
        for pillar in PILLARS:
            chunks = pillar_chunks.get(pillar, [])
            if not chunks:
                continue
            part = await self.extract_for_pillar(
                filename=filename,
                pillar=pillar,
                chunks=chunks,
                pillar_status={pillar: pillar_status[pillar]},
            )
            if not merged.document_title and part.document_title:
                merged.document_title = part.document_title
            if not merged.reporting_entity and part.reporting_entity:
                merged.reporting_entity = part.reporting_entity
            if not merged.reporting_year and part.reporting_year:
                merged.reporting_year = part.reporting_year
            merged.claims.extend(part.claims)
            merged.extraction_notes.extend(part.extraction_notes)
        return merged

    async def _call_llm(self, user_content: str) -> ExtractionResponse:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        last_error: str | None = None
        for attempt in range(2):
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

            resp = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=8192,
                temperature=0,
                response_format={"type": "json_object"},
                messages=messages,
            )
            raw = resp.choices[0].message.content or ""
            try:
                payload = json.loads(_strip_json_fence(raw))
                return ExtractionResponse.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)

        raise ValueError(f"Extraction failed after retry: {last_error}")
