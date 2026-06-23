"""Pydantic models for LLM extraction output (validated before DB insert)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from greengag.models.schemas import EsgPillar, ExtractedClaim, HighlightBox


class LlmClaim(BaseModel):
    id: str
    pillar: EsgPillar
    category: str
    claim_type: str
    label: str
    raw_text: str
    entity: str | None = None
    metric: str | None = None
    target_value: str | None = None
    achieved_value: str | None = None
    baseline_value: str | None = None
    time_period: str | None = None
    location: str | None = None
    unit: str | None = None
    page: int | None = None
    section_heading: str | None = None
    key_metrics: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ExtractionResponse(BaseModel):
    document_title: str | None = None
    reporting_entity: str | None = None
    reporting_year: str | None = None
    claims: list[LlmClaim] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)


class PillarRetrievalStatus(BaseModel):
    status: Literal["ok", "insufficient_text_retrieved"]
    best_score: float
    chunks_selected: int


class RetrievedChunk(BaseModel):
    id: str
    content: str
    page: int | None
    section_heading: str | None
    pillar_hint: str | None
    vector_score: float
    hybrid_score: float
    matched_pillar: EsgPillar


class TextChunk(BaseModel):
    chunk_index: int
    page: int
    section_heading: str | None
    pillar_hint: str | None
    content: str
    token_estimate: int


def _parse_float_from_text(value: str | None) -> float | None:
    if not value:
        return None
    import re

    m = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
    return float(m.group(1)) if m else None


def llm_claim_to_extracted(claim: LlmClaim) -> ExtractedClaim:
    """Map validated LLM claim → shared ExtractedClaim contract."""
    km = claim.key_metrics
    reduction = km.get("reduction_target_pct") or km.get("claimed_reduction_pct")
    if isinstance(reduction, str):
        reduction = _parse_float_from_text(reduction)
    elif isinstance(reduction, (int, float)):
        reduction = float(reduction)
    else:
        reduction = _parse_float_from_text(claim.target_value)

    material = claim.material_class if hasattr(claim, "material_class") else None
    if not material and claim.claim_type == "low_carbon_materials":
        material = km.get("material_class") or claim.metric

    spend = km.get("stated_spend_usd") or km.get("green_budget_usd")
    if isinstance(spend, str):
        spend = _parse_float_from_text(spend)
    elif isinstance(spend, (int, float)):
        spend = float(spend)

    highlight = None
    if claim.page is not None:
        highlight = HighlightBox(page=claim.page, x=8.0, y=30.0, w=84.0, h=9.0)

    return ExtractedClaim(
        id=claim.id,
        label=claim.label,
        raw_text=claim.raw_text,
        pillar=claim.pillar,
        category=claim.category,
        claim_type=claim.claim_type,
        entity=claim.entity,
        metric=claim.metric,
        target_value=claim.target_value,
        achieved_value=claim.achieved_value,
        baseline_value=claim.baseline_value,
        time_period=claim.time_period,
        location=claim.location,
        unit=claim.unit,
        page=claim.page,
        section_heading=claim.section_heading,
        key_metrics=claim.key_metrics,
        confidence=claim.confidence,
        claimed_reduction_pct=reduction,
        material_class=str(material) if material else None,
        stated_spend_usd=spend,
        highlight=highlight,
    )
