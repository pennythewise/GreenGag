"""Deterministic measurable-claim candidates.

The LLM is allowed to normalize these rows, but not decide the claim count.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from models.schemas import EsgPillar
from providers.local_embedder import encode_texts

from .claim_rules import extract_units, matches_claim_regex
from .models import ClaimCandidate, LlmClaim, RetrievedChunk
from ..rag.pillar_queries import PILLAR_QUERIES, PILLARS

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'“”A-Z0-9])")
WHITESPACE_RE = re.compile(r"\s+")
FISCAL_YEAR_RE = re.compile(r"\bFY\s?\d{2,4}\b", re.IGNORECASE)
TARGET_RE = re.compile(r"\bby\s+(FY\s?\d{2,4}|20\d{2})\b", re.IGNORECASE)
PERCENT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*%")

SENTENCE_PILLAR_PROTOTYPES: dict[EsgPillar, tuple[str, ...]] = {
    "environment": (
        PILLAR_QUERIES["environment"],
        "renewable electricity energy consumption offices data centers percent target",
        "scope 1 scope 2 greenhouse gas emissions reduction target net zero climate",
        "water waste recycling landfill biodiversity environmental controls",
    ),
    "social": (
        PILLAR_QUERIES["social"],
        "supplier audits forced labor human rights VAP strategic suppliers labor standards",
        "employee safety injuries fatalities training workforce diversity gender",
        "community investment scholarships students local employment social impact",
    ),
    "governance": (
        PILLAR_QUERIES["governance"],
        "board oversight independent directors ESG committee governance accountability",
        "anti corruption ethics compliance whistleblower policy risk management",
        "ESG assurance disclosure quality materiality assessment reporting standards",
    ),
}


def candidates_for_pillar(
    pillar: EsgPillar,
    chunks: list[RetrievedChunk],
) -> list[ClaimCandidate]:
    """Return stable candidates classified to the pillar by MiniLM."""
    seen: set[str] = set()
    raw_candidates: list[tuple[str, str, RetrievedChunk]] = []

    for chunk in chunks:
        for sentence in _sentences(chunk.content):
            raw_text = sentence.strip(" \t\r\n-•")
            key = _normalize_key(raw_text)
            if not key or key in seen or not matches_claim_regex(raw_text):
                continue

            seen.add(key)
            raw_candidates.append((key, raw_text, chunk))

    if not raw_candidates:
        return []

    sentence_scores = _score_sentence_pillars([raw for _, raw, _ in raw_candidates])
    candidates: list[ClaimCandidate] = []

    for (key, raw_text, chunk), pillar_scores in zip(raw_candidates, sentence_scores):
        matched_pillar = max(pillar_scores, key=pillar_scores.get)
        if matched_pillar != pillar:
            continue

        candidate_id = f"{pillar}-{hashlib.sha1(key.encode()).hexdigest()[:10]}"
        candidates.append(
            ClaimCandidate(
                id=candidate_id,
                pillar=pillar,
                raw_text=raw_text,
                page=chunk.page,
                section_heading=chunk.section_heading,
                chunk_id=chunk.id,
                routing_score=pillar_scores[pillar],
            )
        )

    return candidates


def fallback_claim_from_candidate(candidate: ClaimCandidate) -> LlmClaim:
    category, claim_type, metric = _classify_candidate(candidate.pillar, candidate.raw_text)
    target_value, achieved_value, time_period, unit = _extract_basic_values(candidate.raw_text)
    return LlmClaim(
        id=candidate.id,
        pillar=candidate.pillar,
        category=category,
        claim_type=claim_type,
        label=_label_from_text(candidate.raw_text, metric),
        raw_text=candidate.raw_text,
        metric=metric,
        target_value=target_value,
        achieved_value=achieved_value,
        time_period=time_period,
        unit=unit,
        page=candidate.page,
        section_heading=candidate.section_heading,
        key_metrics={"candidate_source": "deterministic_regex"},
        confidence=1.0,
    )


def _sentences(text: str) -> list[str]:
    cleaned = WHITESPACE_RE.sub(" ", text).strip()
    if not cleaned:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(cleaned) if len(s.strip()) >= 12]


def _normalize_key(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text.lower()).strip(" \"'“”.,;:")


def _score_sentence_pillars(sentences: list[str]) -> list[dict[EsgPillar, float]]:
    query_texts = [
        prototype
        for pillar in PILLARS
        for prototype in SENTENCE_PILLAR_PROTOTYPES[pillar]
    ]
    vectors = encode_texts([*query_texts, *sentences])
    query_vectors = vectors[: len(query_texts)]
    sentence_vectors = vectors[len(query_texts) :]

    prototype_offsets: dict[EsgPillar, range] = {}
    offset = 0
    for pillar in PILLARS:
        count = len(SENTENCE_PILLAR_PROTOTYPES[pillar])
        prototype_offsets[pillar] = range(offset, offset + count)
        offset += count

    scored: list[dict[EsgPillar, float]] = []
    for sentence_vec in sentence_vectors:
        scored.append(
            {
                pillar: max(
                    _normalized_cosine(query_vectors[idx], sentence_vec)
                    for idx in prototype_offsets[pillar]
                )
                for pillar in PILLARS
            }
        )
    return scored


def _normalized_cosine(a: np.ndarray, b: np.ndarray) -> float:
    return round((float(np.dot(a, b)) + 1.0) / 2.0, 4)


def _classify_candidate(pillar: EsgPillar, text: str) -> tuple[str, str, str]:
    lower = text.lower()

    if pillar == "environment":
        if "renewable" in lower or "electricity" in lower or "energy" in lower:
            return "Energy Management", "energy_consumption", "renewable electricity use"
        if "scope 1" in lower or "scope 2" in lower or "emission" in lower or "ghg" in lower:
            return "Climate Action — GHG", "ghg_scope12_intensity", "scope 1 and 2 emissions"
        if "net zero" in lower or "net-zero" in lower:
            return "Climate Action — GHG", "net_zero_commitment", "net zero commitment"
        if "water" in lower:
            return "Water Stewardship", "water_efficiency", "water efficiency"
        if "waste" in lower or "landfill" in lower:
            return "Waste Management", "waste_diversion", "waste diversion"
        return "Environment", "other", "environmental metric"

    if pillar == "social":
        if "supplier" in lower or "labor" in lower or "labour" in lower or "vap" in lower:
            return "Supply Chain and Economic Responsibility", "supply_chain_esg", "supplier audits"
        if "safety" in lower or "injur" in lower or "fatalit" in lower:
            return "Workforce Health, Safety and Wellbeing", "safety_performance", "safety performance"
        if "women" in lower or "diversity" in lower or "gender" in lower:
            return "Diversity, Equity and Inclusion", "dei_women_empowerment", "diversity metric"
        if "training" in lower or "employee" in lower:
            return "Human Capital Development", "training_development", "employee training"
        return "Social", "other", "social metric"

    if "board" in lower or "committee" in lower:
        return "ESG Governance and Accountability", "board_esg_oversight", "board ESG oversight"
    if "assurance" in lower or "audit" in lower:
        return "Data Governance and Disclosure Quality", "esg_assurance", "ESG assurance"
    if "anti-corruption" in lower or "ethics" in lower or "whistle" in lower:
        return "Business Ethics and Compliance", "anti_corruption", "ethics and compliance"
    return "Governance", "other", "governance metric"


def _extract_basic_values(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    percentages = PERCENT_RE.findall(text)
    target_match = TARGET_RE.search(text)
    fy_match = FISCAL_YEAR_RE.search(text)
    units = extract_units(text)

    target_value = percentages[0] if percentages and target_match else None
    achieved_value = percentages[0] if percentages and not target_match else None
    time_period = target_match.group(0) if target_match else (fy_match.group(0) if fy_match else None)
    unit = "%" if percentages else (units[0] if units else None)
    return target_value, achieved_value, time_period, unit


def _label_from_text(text: str, metric: str) -> str:
    if "renewable electricity" in text.lower():
        return "100% renewable electricity use for offices and data centers"
    if "scope 1" in text.lower() and "scope 2" in text.lower():
        return "Scope 1 and 2 emissions reduction target"
    return metric[:1].upper() + metric[1:]
