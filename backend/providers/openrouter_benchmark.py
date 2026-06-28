"""Live industry benchmarking via OpenRouter (google/gemini-2.5-flash:online)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from config import settings
from models.schemas import ExtractedClaim
from providers.construction_peer_registry import (
    ConstructionBenchmarkContext,
    resolve_benchmark_context,
)

logger = logging.getLogger("greengag.openrouter_benchmark")

ALLOWED_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)
URL_RE = re.compile(r"https?://[^\s\])\"']+")


@dataclass(frozen=True)
class BenchmarkEvidence:
    score: float
    contradiction: bool
    evidence_snippets: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    rationale: str = ""
    used_live_search: bool = False
    provider: str = "none"
    peer_context: ConstructionBenchmarkContext | None = None


async def benchmark_claim_live(
    claim: ExtractedClaim,
    *,
    reporting_entity: str | None = None,
) -> BenchmarkEvidence | None:
    if not settings.live_benchmark_ready():
        return None

    context = resolve_benchmark_context(
        reporting_entity=reporting_entity,
        claim_entity=claim.entity,
    )
    if not context.profile_resolved:
        return _unresolved_profile_evidence(context)

    return await asyncio.to_thread(_benchmark_claim_sync, claim, context)


def _unresolved_profile_evidence(
    context: ConstructionBenchmarkContext,
) -> BenchmarkEvidence:
    return BenchmarkEvidence(
        score=0.25,
        contradiction=False,
        evidence_snippets=[
            f"No local construction peer profile found for {context.canonical_name}."
        ],
        sources=["GreenGag construction peer registry"],
        rationale=(
            f"Benchmark skipped live web search because {context.canonical_name} is not "
            "in the local Malaysian construction peer registry. Add the company profile "
            "in backend/data/construction_company_profiles.json before comparing peers."
        ),
        used_live_search=False,
        provider="registry:unresolved",
        peer_context=context,
    )


def _benchmark_claim_sync(
    claim: ExtractedClaim,
    context: ConstructionBenchmarkContext,
) -> BenchmarkEvidence | None:
    if not settings.openrouter_api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    model = settings.openrouter_online_model
    prompt = _prompt(claim, context)
    try:
        client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an ESG industry benchmarking agent for Malaysian "
                        "construction companies with live web access. Compare claims "
                        "only against the allowed peer universe provided. Never use "
                        "companies from excluded categories as peers. Return ONLY valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        logger.warning("OpenRouter live benchmark failed: %s", exc)
        return None

    message = response.choices[0].message
    text = message.content or ""
    payload = _parse_json(text)
    if not payload:
        return None

    sources = _extract_urls(text)
    sources.extend(str(s) for s in payload.get("sources", []) if s)
    if hasattr(message, "annotations") and message.annotations:
        for annotation in message.annotations:
            url = getattr(annotation, "url", None) or getattr(
                getattr(annotation, "url_citation", None), "url", None
            )
            if url:
                sources.append(str(url))

    peer_names_used = [
        str(name).strip()
        for name in payload.get("peers_used", [])
        if str(name).strip()
    ]
    invalid_peers = _invalid_peer_names(peer_names_used, context)
    score = _nearest_score(payload.get("score"))
    contradiction = bool(payload.get("contradiction", False))
    rationale = str(
        payload.get("rationale")
        or f"OpenRouter live benchmark completed via {model}."
    )
    if invalid_peers:
        score = min(score, 0.25)
        rationale = (
            f"Rejected out-of-universe peers: {', '.join(invalid_peers)}. {rationale}"
        )

    return BenchmarkEvidence(
        score=score,
        contradiction=contradiction,
        evidence_snippets=[
            str(s).strip()
            for s in payload.get("evidence_snippets", [])
            if str(s).strip()
        ][:3],
        sources=_dedupe(sources)[:5],
        rationale=(
            f"Target profile: {context.canonical_name} ({context.subsector}). {rationale}"
        ),
        used_live_search=True,
        provider=f"openrouter:{model}",
        peer_context=context,
    )


def _prompt(claim: ExtractedClaim, context: ConstructionBenchmarkContext) -> str:
    peer_lines = "\n".join(f"- {name}" for name in context.allowed_peer_names) or "- none configured"
    excluded_lines = "\n".join(f"- {item}" for item in context.excluded_peer_categories)
    product_lines = "\n".join(f"- {item}" for item in context.products_services) or "- not specified"

    return f"""
You are benchmarking one ESG claim for a Malaysian construction company.
Use live web evidence when available. Return ONLY JSON.

Target company profile:
- canonical_name: {context.canonical_name}
- country: {context.country}
- sector: {context.sector}
- subsector: {context.subsector}
- products_services:
{product_lines}

Allowed peer universe (ONLY compare against these companies):
{peer_lines}

Excluded peer categories (NEVER use these as peers):
{excluded_lines}

Hard rules:
1. Do not benchmark against companies outside the allowed peer universe.
2. Do not use cement/materials-only companies, plantations, utilities, telcos, banks, or unrelated conglomerates as peers.
3. Prefer peers with the same construction subsector and comparable ESG metric.
4. If no credible peer evidence exists in the allowed universe, return score 0.25 and explain insufficient peer evidence.
5. List the peer companies you actually used in peers_used.

Claim:
- label: {claim.label}
- raw_text: {claim.raw_text}
- pillar: {claim.pillar}
- category: {claim.category}
- claim_type: {claim.claim_type}
- metric: {claim.metric}
- target_value: {claim.target_value}
- achieved_value: {claim.achieved_value}
- baseline_value: {claim.baseline_value}
- time_period: {claim.time_period}
- unit: {claim.unit}
- entity: {claim.entity}

Task:
1. Find whether the claim value is plausible compared with allowed Malaysian construction peers.
2. Detect contradiction if credible public evidence conflicts with the claim.
3. Assign score using only: 0, 0.25, 0.5, 0.75, 1.

Score rubric:
- 1.0: same/comparable metric found and claim is within plausible peer range.
- 0.75: comparable metric found; claim is outside range but not contradicted.
- 0.5: related peer evidence found but metric/unit is only partially comparable.
- 0.25: weak or insufficient peer evidence within the allowed universe.
- 0.0: direct contradiction or clearly invalid peer comparison attempted.

Return JSON exactly:
{{
  "score": 0.75,
  "contradiction": false,
  "peers_used": ["Peer Company Name"],
  "evidence_snippets": ["short evidence sentence"],
  "sources": ["source name or URL"],
  "rationale": "one concise explanation"
}}
""".strip()


def _invalid_peer_names(
    peers_used: list[str],
    context: ConstructionBenchmarkContext,
) -> list[str]:
    if not peers_used:
        return []
    allowed = {_normalize_peer_name(name) for name in context.allowed_peer_names}
    allowed.add(_normalize_peer_name(context.canonical_name))
    invalid: list[str] = []
    for peer in peers_used:
        if _normalize_peer_name(peer) not in allowed:
            invalid.append(peer)
    return invalid


def _normalize_peer_name(value: str) -> str:
    cleaned = value.lower().strip()
    for suffix in (" berhad", " bhd", " sdn bhd", " group"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return re.sub(r"[^a-z0-9]+", "", cleaned)


def _parse_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _nearest_score(value: Any) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.25
    return min(ALLOWED_SCORES, key=lambda score: abs(score - raw))


def _extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in URL_RE.findall(text):
        parsed = urlparse(match.rstrip(".,;)"))
        if parsed.scheme and parsed.netloc:
            urls.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}")
    return urls


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
