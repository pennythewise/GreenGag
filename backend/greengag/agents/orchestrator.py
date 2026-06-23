"""Agent 1 — Orchestrator (The Supervisor).

Coordinates state flow across the four sub-agents using LangGraph (with a
sequential fallback), collects risk contributions, and applies the Weighted
Integrity Index via greengag.scoring.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator
from typing import Any, TypedDict

from greengag.mocks import fixtures
from greengag.models.schemas import (
    AgentStates,
    AuditPayload,
    GeospatialTruthState,
    GlobalMetrics,
    LedgerAuditorState,
    MediaSentinelState,
    ReportParserState,
)
from greengag.scoring.integrity import compute_global_metrics

from .geospatial_truth import GeospatialTruthAgent
from .ledger_auditor import LedgerAuditorAgent
from .media_sentinel import MediaSentinelAgent
from .report_parser import ReportParserAgent

try:
    from langgraph.graph import END, START, StateGraph

    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover
    _HAS_LANGGRAPH = False


AGENT_SEQUENCE = [
    ("ReportParserAgent", ReportParserAgent),
    ("LedgerAuditorAgent", LedgerAuditorAgent),
    ("MediaSentinelAgent", MediaSentinelAgent),
    ("GeospatialTruthAgent", GeospatialTruthAgent),
]


def _assemble(states: AgentStates) -> AuditPayload:
    return AuditPayload(
        audit_id=fixtures.AUDIT_ID,
        meta=fixtures.META,
        agent_states=states,
        discrepancies=copy.deepcopy(fixtures.DISCREPANCIES),
        global_metrics=compute_global_metrics(states),
    )


class GraphState(TypedDict, total=False):
    ReportParserAgent: ReportParserState
    LedgerAuditorAgent: LedgerAuditorState
    MediaSentinelAgent: MediaSentinelState
    GeospatialTruthAgent: GeospatialTruthState


def _build_graph():
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


async def stream_audit() -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-ready events as each agent transitions."""
    states = AgentStates()

    def snapshot(payload_global: GlobalMetrics | None = None) -> AuditPayload:
        return AuditPayload(
            audit_id=fixtures.AUDIT_ID,
            meta=fixtures.META,
            agent_states=copy.deepcopy(states),
            discrepancies=copy.deepcopy(fixtures.DISCREPANCIES),
            global_metrics=payload_global
            or GlobalMetrics(executive_summary="Awaiting agent findings..."),
        )

    yield {"type": "global_update", "payload": snapshot().model_dump()}

    for key, AgentCls in AGENT_SEQUENCE:
        agent = AgentCls()

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

        final_state = await agent.run()
        setattr(states, key, final_state)
        yield {
            "type": "agent_update",
            "agent": key,
            "payload": snapshot().model_dump(),
        }
        await asyncio.sleep(0.15)

    yield {"type": "complete", "payload": _assemble(states).model_dump()}


def _tool_hint(key: str) -> str:
    return {
        "ReportParserAgent": "pdf_extractor::gpt-4o",
        "LedgerAuditorAgent": "ledger_query::postgres(internal)",
        "MediaSentinelAgent": "web_scraper::nlp-classifier",
        "GeospatialTruthAgent": "sentinel5p::tropomi-no2",
    }[key]
