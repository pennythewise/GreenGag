"""Selected-claim verification using a deterministic weighted evidence framework."""

from __future__ import annotations

import re
from typing import Any

from models.schemas import (
    EvidenceLayerKey,
    EvidenceLayerScore,
    ExtractedClaim,
    PeerIntensityRow,
    VerificationRunResponse,
    WeightedVerificationState,
)
from providers.openrouter_benchmark import benchmark_claim_live

from .base import BaseAgent

CONTRADICTION_SCORE_CAP = 0.40

WEIGHTS: dict[EvidenceLayerKey, float] = {
    "official_report": 0.25,
    "financial_statements": 0.30,
    "historical_consistency": 0.15,
    "methodology": 0.15,
    "industry_benchmark": 0.15,
}

LABELS: dict[EvidenceLayerKey, str] = {
    "official_report": "Official sustainability report",
    "financial_statements": "Audited financial statements / annual report",
    "historical_consistency": "Historical consistency",
    "methodology": "Methodology verification",
    "industry_benchmark": "Industry benchmarking",
}

METHODOLOGY_TERMS = (
    "ghg protocol",
    "iso 14064-1",
    "iso 14064",
    "defra",
    "ipcc",
    "iea",
    "location-based",
    "market-based",
)

GENERIC_METHOD_TERMS = (
    "methodology",
    "emission factor",
    "calculation",
    "basis of preparation",
    "reporting boundary",
)

YEAR_RE = re.compile(r"\b(?:FY\s?\d{2,4}|20\d{2})\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


class WeightedConfidenceAgent(BaseAgent):
    key = "WeightedConfidenceAgent"
    name = "Weighted Confidence Agent"
    mock_latency = 0.2

    async def _run_mock(self) -> WeightedVerificationState:
        return WeightedVerificationState(
            status="IDLE",
            progress=0.0,
            active_tool="weighted_confidence::deterministic_rules",
            rationale_trail=["Awaiting a selected extracted claim."],
        )

    async def verify(
        self,
        *,
        document_id: str,
        claim: ExtractedClaim | dict[str, Any],
        chunks: list[dict[str, Any]],
        reporting_entity: str | None = None,
        persist_run_id: str | None = None,
        created_at: str | None = None,
        mode: str = "live",
    ) -> VerificationRunResponse:
        claim_model = (
            claim if isinstance(claim, ExtractedClaim) else ExtractedClaim.model_validate(claim)
        )
        chunk_texts = [str(c.get("content", "")) for c in chunks]

        layer_scores = [
            self._score_official_report(claim_model, chunks),
            self._score_financial_statements(claim_model, chunk_texts),
            self._score_historical_consistency(claim_model, chunk_texts),
            self._score_methodology(claim_model, chunk_texts),
            await self._score_industry_benchmark(claim_model, reporting_entity),
        ]
        uncapped = round(sum(layer.weight * layer.score for layer in layer_scores), 3)
        contradiction = self._detect_contradiction(claim_model, chunk_texts) or any(
            layer.contradiction for layer in layer_scores
        )
        cap_applied = contradiction and uncapped > CONTRADICTION_SCORE_CAP
        overall = CONTRADICTION_SCORE_CAP if cap_applied else uncapped
        rationale = [
            (
                f"Verified selected claim {claim_model.id} with deterministic "
                "0/0.25/0.5/0.75/1 layer scoring."
            ),
            "Used uploaded sustainability report evidence first; external financial and peer layers use MVP mock fallbacks where needed.",
            f"Overall weighted confidence score: {round(overall * 100)}%.",
        ]
        if contradiction:
            rationale.append(
                "Contradiction flag raised; overall score is capped at 40% when the uncapped score exceeds the cap."
            )

        return VerificationRunResponse(
            id=persist_run_id or "pending",
            document_id=document_id,
            claim_id=claim_model.id,
            overall_score=overall,
            uncapped_score=uncapped,
            contradiction_flag=contradiction,
            score_cap_applied=cap_applied,
            score_cap_reason=(
                "Contradictory benchmark or source evidence found; confidence capped at 40%."
                if cap_applied
                else None
            ),
            layer_scores=layer_scores,
            rationale_trail=rationale,
            mode=mode,
            created_at=created_at,
        )

    def _score_official_report(
        self,
        claim: ExtractedClaim,
        chunks: list[dict[str, Any]],
    ) -> EvidenceLayerScore:
        source = "Uploaded sustainability report"
        snippets = _matching_snippets(claim.raw_text, chunks)
        if snippets:
            has_supporting_fields = _supporting_claim_fields_present(claim, snippets)
            score = 1.0 if has_supporting_fields else 0.75
            rationale = (
                "Claim text and structured supporting values were found in the uploaded sustainability report."
                if has_supporting_fields
                else "Claim text was found in the uploaded sustainability report, but supporting structured values were limited."
            )
            missing = False
        else:
            score = 0.5
            snippets = [claim.raw_text]
            rationale = "Claim exists in extracted claims but exact source text was not located in retrieved chunks."
            missing = False
        return _layer("official_report", score, snippets, [source], rationale, missing)

    def _score_financial_statements(
        self,
        claim: ExtractedClaim,
        chunk_texts: list[str],
    ) -> EvidenceLayerScore:
        haystack = _join(chunk_texts)
        financial_terms = ("revenue", "rm million", "annual report", "financial statements", "capex", "opex")
        has_denominator = any(term in haystack for term in financial_terms) or bool(
            claim.stated_spend_usd
        )
        has_audited_source = any(
            term in haystack for term in ("annual report", "financial statements", "audited")
        )
        if has_denominator:
            score = 1.0 if has_audited_source else 0.75
            return _layer(
                "financial_statements",
                score,
                [_first_term_snippet(haystack, financial_terms) or claim.raw_text],
                ["Uploaded sustainability report"],
                (
                    "Audited financial-statement context and denominator/activity-scale evidence are disclosed."
                    if has_audited_source
                    else "Financial denominator or activity-scale context is disclosed, but audited statement linkage is indirect."
                ),
                False,
            )
        return _layer(
            "financial_statements",
            0.25,
            [_mock_financial_snippet(claim)],
            ["MVP mock annual-report evidence"],
            "No audited financial statement source is connected yet; MVP mock fallback provides minimal activity-scale plausibility only.",
            True,
        )

    def _score_historical_consistency(
        self,
        claim: ExtractedClaim,
        chunk_texts: list[str],
    ) -> EvidenceLayerScore:
        text = " ".join([claim.raw_text, *chunk_texts])
        years = sorted(set(YEAR_RE.findall(text)))
        if claim.baseline_value and len(years) >= 3:
            return _layer(
                "historical_consistency",
                1.0,
                [_history_snippet(claim, years)],
                ["Uploaded sustainability report"],
                "Claim includes baseline and multi-year context suitable for a robust consistency check.",
                False,
            )
        if claim.baseline_value or len(years) >= 3:
            return _layer(
                "historical_consistency",
                0.75,
                [_history_snippet(claim, years)],
                ["Uploaded sustainability report"],
                "Claim includes either baseline evidence or enough multi-year context for a strong partial consistency check.",
                False,
            )
        if claim.time_period or years:
            return _layer(
                "historical_consistency",
                0.5,
                [_history_snippet(claim, years)],
                ["Uploaded sustainability report"],
                "Claim includes limited time context but not enough prior-year evidence for a full trend check.",
                False,
            )
        if _claim_number(claim) is not None:
            return _layer(
                "historical_consistency",
                0.25,
                [claim.raw_text],
                ["Uploaded sustainability report"],
                "Claim has a measurable value but no baseline or trend evidence.",
                True,
            )
        return _layer(
            "historical_consistency",
            0.0,
            [],
            [],
            "No baseline, prior year, or time period evidence was available.",
            True,
        )

    def _score_methodology(
        self,
        claim: ExtractedClaim,
        chunk_texts: list[str],
    ) -> EvidenceLayerScore:
        text = _join(chunk_texts)
        matched = [term for term in METHODOLOGY_TERMS if term in text]
        generic = [term for term in GENERIC_METHOD_TERMS if term in text]
        if matched and generic:
            return _layer(
                "methodology",
                1.0,
                [f"Recognized methodology disclosed: {', '.join(matched[:4])}."],
                ["Uploaded sustainability report"],
                "Report references recognized standards and describes calculation/methodology context.",
                False,
            )
        if matched:
            return _layer(
                "methodology",
                0.75,
                [f"Recognized methodology disclosed: {', '.join(matched[:4])}."],
                ["Uploaded sustainability report"],
                "Report references internationally recognized standards or factors, but calculation context is limited.",
                False,
            )
        if generic:
            return _layer(
                "methodology",
                0.5,
                [f"Generic methodology terms disclosed: {', '.join(generic[:4])}."],
                ["Uploaded sustainability report"],
                "Report describes methodology but does not clearly cite recognized standards.",
                False,
            )
        if claim.unit or claim.metric or claim.claim_type:
            return _layer(
                "methodology",
                0.25,
                [claim.raw_text],
                ["Uploaded sustainability report"],
                "Claim is measurable, but no explicit methodology or recognized standard was found.",
                True,
            )
        return _layer(
            "methodology",
            0.0,
            [],
            [],
            "No recognized methodology or calculation basis was found.",
            True,
        )

    async def _score_industry_benchmark(
        self,
        claim: ExtractedClaim,
        reporting_entity: str | None = None,
    ) -> EvidenceLayerScore:
        live = await benchmark_claim_live(claim, reporting_entity=reporting_entity)
        if live:
            rationale = live.rationale
            if live.contradiction:
                rationale = f"Contradiction flagged by live benchmark search. {rationale}"

            # Convert peer intensity records to schema rows
            peer_rows: list[PeerIntensityRow] = [
                PeerIntensityRow(
                    company=r.company_name,
                    revenue_rm_million=r.revenue_rm_million,
                    scope_1_2_tco2e=r.scope_1_2_tco2e,
                    scope_3_tco2e=r.scope_3_tco2e,
                    total_scope_123_tco2e=r.total_scope_123_tco2e,
                    intensity_scope_12_per_rm_million=r.intensity_scope_12,
                    intensity_scope_3_per_rm_million=r.intensity_scope_3,
                    intensity_total_per_rm_million=r.intensity_total,
                    intensity_tco2e_per_rm_million=r.intensity_scope_12,
                    data_year=r.data_year,
                    data_found=r.data_found,
                    source=r.source,
                    is_target=r.is_target,
                )
                for r in live.peer_intensity_table
            ]

            layer = _layer(
                "industry_benchmark",
                live.score,
                live.evidence_snippets,
                live.sources or [f"Live benchmark ({live.provider})"],
                rationale,
                not live.used_live_search,
                contradiction=live.contradiction,
            )
            return layer.model_copy(update={
                "peer_table": peer_rows,
                "benchmark_tldr": live.tldr or None,
                "benchmark_insights": live.insights or None,
                "benchmark_conclusion": live.conclusion or None,
                "benchmark_unit": live.benchmark_unit if live.is_ghg_claim else None,
                "peer_intensity_range": live.peer_intensity_range or None,
            })

        comparable_value = _claim_number(claim)
        benchmark = _mock_benchmark_range(claim)
        if benchmark and comparable_value is not None:
            low, high, unit = benchmark
            in_range = low <= comparable_value <= high
            score = 1.0 if in_range else 0.75
            rationale = (
                f"Claim value {comparable_value:g}{unit} is within the MVP peer range."
                if in_range
                else f"Claim value {comparable_value:g}{unit} is outside the MVP peer range but remains directly comparable."
            )
            return _layer(
                "industry_benchmark",
                score,
                [f"MVP peer range for {claim.claim_type or 'metric'}: {low:g}-{high:g}{unit}."],
                ["MVP mock peer benchmark dataset"],
                rationale,
                False,
            ).model_copy(update={
                "benchmark_tldr": "Live OpenRouter benchmark unavailable; showing MVP mock peer range.",
            })
        if claim.unit or claim.metric:
            return _layer(
                "industry_benchmark",
                0.25,
                [f"Comparable metric available: {claim.metric or claim.claim_type or 'ESG metric'}."],
                ["MVP mock peer benchmark dataset"],
                "Claim has a comparable metric/unit, but no peer range is configured yet.",
                True,
            ).model_copy(update={
                "benchmark_tldr": "Live OpenRouter benchmark unavailable; limited mock comparison only.",
            })
        return _layer(
            "industry_benchmark",
            0.0,
            [],
            [],
            "Claim does not expose a comparable benchmark metric.",
            True,
        ).model_copy(update={
            "benchmark_tldr": "No comparable benchmark metric found for this claim.",
        })

    def _detect_contradiction(self, claim: ExtractedClaim, chunk_texts: list[str]) -> bool:
        text = _join([claim.raw_text, *chunk_texts])
        conflict_terms = ("restatement", "not achieved", "missed target", "non-compliance", "violation")
        return any(term in text for term in conflict_terms)


def _layer(
    key: EvidenceLayerKey,
    score: float,
    snippets: list[str],
    sources: list[str],
    rationale: str,
    missing: bool,
    *,
    contradiction: bool = False,
) -> EvidenceLayerScore:
    weight = WEIGHTS[key]
    return EvidenceLayerScore(
        layer_key=key,
        label=LABELS[key],
        weight=weight,
        score=score,
        weighted_score=round(weight * score, 3),
        evidence_snippets=[s for s in snippets if s][:4],
        sources=sources,
        rationale=rationale,
        missing_evidence=missing,
        contradiction=contradiction,
    )


def _join(parts: list[str]) -> str:
    return " ".join(parts).lower()


def _matching_snippets(raw_text: str, chunks: list[dict[str, Any]]) -> list[str]:
    needle = _compact(raw_text)
    if not needle:
        return []
    snippets: list[str] = []
    for chunk in chunks:
        content = str(chunk.get("content", ""))
        if needle in _compact(content):
            snippets.append(content[:600])
    return snippets


def _supporting_claim_fields_present(claim: ExtractedClaim, snippets: list[str]) -> bool:
    text = _compact(" ".join(snippets))
    fields = [
        claim.target_value,
        claim.achieved_value,
        claim.baseline_value,
        claim.time_period,
        claim.unit,
    ]
    compact_fields = [_compact(str(value)) for value in fields if value]
    return any(value and value in text for value in compact_fields)


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _first_term_snippet(text: str, terms: tuple[str, ...]) -> str | None:
    for term in terms:
        idx = text.find(term)
        if idx >= 0:
            start = max(0, idx - 140)
            end = min(len(text), idx + 220)
            return text[start:end].strip()
    return None


def _history_snippet(claim: ExtractedClaim, years: list[str]) -> str:
    bits = []
    if claim.baseline_value:
        bits.append(f"baseline={claim.baseline_value}")
    if claim.time_period:
        bits.append(f"time_period={claim.time_period}")
    if years:
        bits.append(f"years={', '.join(years[:5])}")
    return "; ".join(bits) if bits else claim.raw_text


def _mock_financial_snippet(claim: ExtractedClaim) -> str:
    entity = claim.entity or "the reporting entity"
    return (
        f"MVP fallback: audited financial-statement adapter not connected; "
        f"{entity} activity scale is treated as partially corroborated for this claim type."
    )


def _claim_number(claim: ExtractedClaim) -> float | None:
    values = [
        claim.achieved_value,
        claim.target_value,
        claim.baseline_value,
        str(claim.claimed_reduction_pct) if claim.claimed_reduction_pct is not None else None,
    ]
    for value in values:
        if not value:
            continue
        match = NUMBER_RE.search(value.replace(",", ""))
        if match:
            return float(match.group(0))
    return None


def _mock_benchmark_range(claim: ExtractedClaim) -> tuple[float, float, str] | None:
    claim_type = claim.claim_type or ""
    metric = (claim.metric or "").lower()
    if claim_type in {"energy_consumption", "renewable_energy"} or "renewable" in metric:
        return (20.0, 100.0, "%")
    if claim_type in {"ghg_scope12_intensity", "net_zero_commitment"}:
        return (5.0, 100.0, "%")
    if claim_type in {"water_efficiency", "waste_diversion"}:
        return (0.0, 100.0, "%")
    if claim_type in {"safety_performance", "supply_chain_esg"}:
        return (0.0, 100.0, "%")
    return None
