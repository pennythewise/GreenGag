"""Agent 1 — Orchestrator (The Supervisor).

Central traffic controller. Coordinates state flow across the four sub-agents
using a LangGraph directional graph (with a sequential fallback if LangGraph is
not installed), collects each agent's risk_contribution, and applies the
Weighted Integrity Index — 50% weight to physical/satellite data, with the
GeospatialTruthAgent holding absolute veto power.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator
from typing import Any, TypedDict

from mocks import fixtures
from models.schemas import (
    AgentStates,
    AuditPayload,
    GeospatialTruthState,
    GlobalMetrics,
    LedgerAuditorState,
    MediaSentinelState,
    ReportParserState,
)

from .geospatial_truth import GeospatialTruthAgent
from .ledger_auditor import LedgerAuditorAgent
from .media_sentinel import MediaSentinelAgent
from .report_parser import ReportParserAgent

try:
    from langgraph.graph import END, START, StateGraph

    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_LANGGRAPH = False


AGENT_SEQUENCE = [
    ("ReportParserAgent", ReportParserAgent),
    ("LedgerAuditorAgent", LedgerAuditorAgent),
    ("MediaSentinelAgent", MediaSentinelAgent),
    ("GeospatialTruthAgent", GeospatialTruthAgent),
]


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
    # Confidence: average across all satellite layers, fallback 0.8
    if geo.metrics and geo.metrics.layers:
        geo_conf = sum(l.confidence_index for l in geo.metrics.layers) / len(geo.metrics.layers)
    else:
        geo_conf = 0.8
    confidence = round(geo_conf * 0.96, 3)

    # Resolve verdict; the geospatial veto escalates the floor.
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
        verdict = "HIGH_RISK"  # physical evidence cannot be outvoted downward

    return GlobalMetrics(
        weighted_risk_score=round(weighted, 3),
        confidence_score=confidence,
        final_verdict=verdict,
        executive_summary=_summarize(states, weighted, veto),
        agent_weights=dict(weights),
    )


def _summarize(states: AgentStates, weighted: float, veto: bool) -> str:
    entity = fixtures.META.target_entity
    geo = states.GeospatialTruthAgent.metrics
    ledger = states.LedgerAuditorAgent.extracted_metrics
    # Use the highest observed variance across all satellite layers.
    if geo and geo.layers:
        top_layer = max(geo.layers, key=lambda l: l.observed_variance_pct)
        variance = f"+{round(top_layer.observed_variance_pct * 100)}% ({top_layer.parameter})"
    else:
        variance = "n/a"
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


def _assemble(states: AgentStates) -> AuditPayload:
    return AuditPayload(
        audit_id=fixtures.AUDIT_ID,
        meta=fixtures.META,
        agent_states=states,
        discrepancies=copy.deepcopy(fixtures.DISCREPANCIES),
        global_metrics=compute_global_metrics(states),
    )


# ── LangGraph supervisor ──────────────────────────────────────────────────


class GraphState(TypedDict, total=False):
    """Channels routed through the supervisor graph — the audit state payload."""

    ReportParserAgent: ReportParserState
    LedgerAuditorAgent: LedgerAuditorState
    MediaSentinelAgent: MediaSentinelState
    GeospatialTruthAgent: GeospatialTruthState


def _build_graph():
    """Build the directional supervisor graph (LangGraph)."""

    async def report_node(state: GraphState) -> GraphState:
        return {"ReportParserAgent": await ReportParserAgent().run()}

    async def ledger_node(state: GraphState) -> GraphState:
        return {"LedgerAuditorAgent": await LedgerAuditorAgent().run()}

    async def media_node(state: GraphState) -> GraphState:
        return {"MediaSentinelAgent": await MediaSentinelAgent().run()}

    async def geo_node(state: GraphState) -> GraphState:
        return {"GeospatialTruthAgent": await GeospatialTruthAgent().run()}

    graph = StateGraph(GraphState)
    graph.add_node("report_parser", report_node)
    graph.add_node("ledger_auditor", ledger_node)
    graph.add_node("media_sentinel", media_node)
    graph.add_node("geospatial_truth", geo_node)

    graph.add_edge(START, "report_parser")
    graph.add_edge("report_parser", "ledger_auditor")
    graph.add_edge("ledger_auditor", "media_sentinel")
    graph.add_edge("media_sentinel", "geospatial_truth")
    graph.add_edge("geospatial_truth", END)
    return graph.compile()


async def run_audit() -> AuditPayload:
    """Run the full audit once and return the assembled payload."""
    if _HAS_LANGGRAPH:
        result = await _build_graph().ainvoke({})
        states = AgentStates(
            ReportParserAgent=result["ReportParserAgent"],
            LedgerAuditorAgent=result["LedgerAuditorAgent"],
            MediaSentinelAgent=result["MediaSentinelAgent"],
            GeospatialTruthAgent=result["GeospatialTruthAgent"],
        )
    else:
        states = AgentStates()
        for key, AgentCls in AGENT_SEQUENCE:
            setattr(states, key, await AgentCls().run())
    return _assemble(states)


# ── Streaming supervisor (drives the live swimlane animation) ─────────────


async def stream_audit() -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-ready events as each agent transitions IDLE -> PROCESSING ->
    SUCCESS/ALERT, then a final compiled verdict. Each event carries a full
    AuditPayload snapshot so the frontend can render incrementally.
    """
    states = AgentStates()

    def snapshot(payload_global: GlobalMetrics | None = None) -> AuditPayload:
        payload = AuditPayload(
            audit_id=fixtures.AUDIT_ID,
            meta=fixtures.META,
            agent_states=copy.deepcopy(states),
            discrepancies=copy.deepcopy(fixtures.DISCREPANCIES),
            global_metrics=payload_global
            or GlobalMetrics(executive_summary="Awaiting agent findings..."),
        )
        return payload

    # Initial blank state.
    yield {"type": "global_update", "payload": snapshot().model_dump()}

    for key, AgentCls in AGENT_SEQUENCE:
        agent = AgentCls()

        # PROCESSING with a climbing progress ring.
        for p in (0.2, 0.55, 0.85):
            current = getattr(states, key)
            current.status = "PROCESSING"
            current.progress = p
            current.active_tool = _tool_hint(key)
            yield {
                "type": "agent_update",
                "agent": key,
                "payload": snapshot().model_dump(),
            }
            await asyncio.sleep(0.18)

        # Settle into final findings.
        final_state = await agent.run()
        setattr(states, key, final_state)
        yield {
            "type": "agent_update",
            "agent": key,
            "payload": snapshot().model_dump(),
        }
        await asyncio.sleep(0.15)

    # Orchestrator compiles the weighted index last.
    final_payload = _assemble(states)
    yield {"type": "complete", "payload": final_payload.model_dump()}


def _tool_hint(key: str) -> str:
    return {
        "ReportParserAgent": "pdf_extractor::claude-opus-4-8",
        "LedgerAuditorAgent": "ledger_query::postgres(internal)",
        "MediaSentinelAgent": "web_scraper::nlp-classifier",
        "GeospatialTruthAgent": "sentinel5p::tropomi-no2",
    }[key]
