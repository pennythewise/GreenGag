"""Deterministic confidence scoring for extracted claims."""

from __future__ import annotations

from config import settings

from .claim_rules import matches_claim_regex
from .models import ClaimCandidate, LlmClaim


def deterministic_confidence(
    *,
    candidate: ClaimCandidate,
    claim: LlmClaim,
    preserved_exact_raw_text: bool,
) -> float:
    score = 0.0

    if matches_claim_regex(candidate.raw_text):
        score += 0.4

    if candidate.routing_score > settings.pillar_routing_confidence_floor:
        score += 0.3

    if any(
        (
            claim.target_value,
            claim.baseline_value,
            claim.time_period,
            claim.unit,
        )
    ):
        score += 0.2

    if preserved_exact_raw_text:
        score += 0.1

    return round(min(score, 1.0), 2)
