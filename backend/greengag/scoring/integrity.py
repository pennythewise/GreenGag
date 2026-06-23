"""Weighted Integrity Index and verdict resolution (deterministic, no LLM)."""

from __future__ import annotations

from greengag.mocks import fixtures
from greengag.models.schemas import AgentStates, GlobalMetrics


def build_executive_summary(states: AgentStates, weighted: float, veto: bool) -> str:
    entity = fixtures.META.target_entity
    geo = states.GeospatialTruthAgent.metrics
    ledger = states.LedgerAuditorAgent.extracted_metrics
    variance = f"+{round(geo.observed_gas_variance_percentage * 100)}%" if geo else "n/a"
    green_ratio = f"{round(ledger.green_ratio * 100)}%" if ledger else "n/a"
    veto_line = (
        " The Geospatial Truth Agent has asserted its veto."
        if veto
        else ""
    )
    return (
        f"{entity}'s decarbonization claim for the {fixtures.META.project_name} is not "
        f"supported by physical, financial, or public evidence. Satellite NO2 readings "
        f"show no reduction ({variance} variance, flatline), while only {green_ratio} of "
        f"procurement spend reached verified green suppliers. Public records contradict "
        f"the zero-incident statement.{veto_line} Weighted risk index: "
        f"{round(weighted * 100)}%."
    )


def compute_global_metrics(states: AgentStates) -> GlobalMetrics:
    """Apply the Weighted Integrity Index and resolve the verdict."""
    weights = fixtures.AGENT_WEIGHTS
    contributions = {
        "ReportParserAgent": states.ReportParserAgent.risk_contribution,
        "LedgerAuditorAgent": states.LedgerAuditorAgent.risk_contribution,
        "MediaSentinelAgent": states.MediaSentinelAgent.risk_contribution,
        "GeospatialTruthAgent": states.GeospatialTruthAgent.risk_contribution,
    }
    weighted = sum(contributions[k] * weights[k] for k in weights)

    geo = states.GeospatialTruthAgent
    veto = bool(geo.metrics and geo.metrics.veto)
    geo_conf = geo.metrics.confidence_index if geo.metrics else 0.8
    confidence = round(geo_conf * 0.96, 3)

    if veto and weighted >= 0.6:
        verdict = "CRITICAL_RISK_FRAUD_DETECTED"
    elif weighted >= 0.66:
        verdict = "HIGH_RISK"
    elif weighted >= 0.4:
        verdict = "MODERATE_RISK"
    elif weighted >= 0.2:
        verdict = "LOW_RISK"
    else:
        verdict = "CLEAR"
    if veto and verdict in ("CLEAR", "LOW_RISK", "MODERATE_RISK"):
        verdict = "HIGH_RISK"

    return GlobalMetrics(
        weighted_risk_score=round(weighted, 3),
        confidence_score=confidence,
        final_verdict=verdict,
        executive_summary=build_executive_summary(states, weighted, veto),
        agent_weights=dict(weights),
    )
