"""Deterministic claim validation (regex now; fine-tuned classifier later)."""

from __future__ import annotations

import re

from models.schemas import EsgPillar

from .models import LlmClaim

# Measurable signal: number + unit, percentage, target year, or commitment + number.
MEASURABLE_CLAIM_RE = re.compile(
    r"(\d+(?:[.,]\d+)?\s*(?:%|percent|percentage|tco2e|tonnes?|tons|kwh|mwh|m³|m3|liters?|usd|\$|rm|million|billion))"
    r"|(\bby\s+20\d{2}\b)"
    r"|(\b(20\d{2})\s*[-–—]\s*(20\d{2})\b)"
    r"|(\b(target|reduce|reduction|commit|committed|achieve|achieved|net[- ]?zero|intensity)\b[^\n]{0,80}\d)",
    re.IGNORECASE,
)

UNIT_NORMALIZE_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(%|tco2e|kwh|mwh|tonnes?|tons|usd|\$|rm)\b",
    re.IGNORECASE,
)


def matches_claim_regex(raw_text: str) -> bool:
    text = raw_text.strip()
    if len(text) < 12:
        return False
    return bool(MEASURABLE_CLAIM_RE.search(text))


def extract_units(raw_text: str) -> list[str]:
    return [m.group(0) for m in UNIT_NORMALIZE_RE.finditer(raw_text)]


def validate_claim_for_pillar(
    claim: LlmClaim,
    *,
    expected_pillar: EsgPillar,
    routing_scores: dict[EsgPillar, float],
    routing_confidence_floor: float,
) -> str | None:
    """Return rejection reason, or None if the claim should be kept."""
    if not matches_claim_regex(claim.raw_text):
        return "raw_text does not match measurable-claim regex"

    if claim.pillar != expected_pillar:
        alt_score = routing_scores.get(claim.pillar, 0.0)
        if alt_score > routing_confidence_floor:
            return None
        return (
            f"pillar '{claim.pillar}' disagrees with extract pillar '{expected_pillar}' "
            f"and routing score {alt_score:.2f} <= {routing_confidence_floor}"
        )

    return None
