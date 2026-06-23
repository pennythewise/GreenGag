"""Pydantic models for the canonical audit state payload.

Single source of truth routed between all agents (CLAUDE.md "Core Data Model").
Mirrors frontend/src/types/audit.ts exactly so the SSE stream deserializes
straight into the React components.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentStatus = Literal["IDLE", "PROCESSING", "SUCCESS", "ALERT"]
FinalVerdict = Literal[
    "CLEAR", "LOW_RISK", "MODERATE_RISK", "HIGH_RISK", "CRITICAL_RISK_FRAUD_DETECTED"
]
AgentKey = Literal[
    "ReportParserAgent",
    "LedgerAuditorAgent",
    "MediaSentinelAgent",
    "GeospatialTruthAgent",
]

EsgPillar = Literal["environment", "social", "governance"]


class GeoPolygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class AuditMeta(BaseModel):
    target_entity: str
    project_name: str
    coordinates: GeoPolygon


class BaseAgentState(BaseModel):
    status: AgentStatus = "IDLE"
    risk_contribution: float = Field(0.0, ge=0.0, le=1.0)
    rationale_trail: list[str] = Field(default_factory=list)
    active_tool: str | None = None
    progress: float = Field(0.0, ge=0.0, le=1.0)


class HighlightBox(BaseModel):
    page: int
    x: float
    y: float
    w: float
    h: float


class ExtractedClaim(BaseModel):
    id: str
    label: str
    raw_text: str
    pillar: EsgPillar | None = None
    category: str | None = None
    claim_type: str | None = None
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
    claimed_reduction_pct: float | None = None
    material_class: str | None = None
    stated_spend_usd: float | None = None
    highlight: HighlightBox | None = None


class PdfBlock(BaseModel):
    id: str
    text: str
    claim_id: str | None = None


class PdfPage(BaseModel):
    page: int
    heading: str
    blocks: list[PdfBlock]


class PdfDocument(BaseModel):
    title: str
    pages: list[PdfPage]


class ReportParserState(BaseAgentState):
    document: PdfDocument | None = None
    extracted_claims: list[ExtractedClaim] = Field(default_factory=list)


class LedgerRow(BaseModel):
    id: str
    date: str
    invoice_id: str
    vendor: str
    material: str
    category: Literal["green", "standard"]
    amount_usd: float
    flagged: bool = False
    linked_claim_id: str | None = None
    note: str | None = None


class LedgerMetrics(BaseModel):
    verified_green_spend_usd: float
    unverified_standard_spend_usd: float
    green_ratio: float


class LedgerAuditorState(BaseAgentState):
    extracted_metrics: LedgerMetrics | None = None
    rows: list[LedgerRow] = Field(default_factory=list)


class MediaArticle(BaseModel):
    id: str
    headline: str
    source: str
    url: str
    published: str
    snippet: str
    contradiction_score: float = Field(ge=0.0, le=1.0)
    tag: Literal["incident", "ngo", "community", "news"]


class MediaSentinelState(BaseAgentState):
    articles: list[MediaArticle] = Field(default_factory=list)


class TimeSeriesPoint(BaseModel):
    date: str
    claimed: float
    observed: float


class HeatPixel(BaseModel):
    lng: float
    lat: float
    intensity: float = Field(ge=0.0, le=1.0)


class GeoMetrics(BaseModel):
    satellite_source: str
    observed_gas_variance_percentage: float
    confidence_index: float
    veto: bool = False


class GeospatialTruthState(BaseAgentState):
    metrics: GeoMetrics | None = None
    unit: str = ""
    time_series: list[TimeSeriesPoint] = Field(default_factory=list)
    heatmap: list[HeatPixel] = Field(default_factory=list)


class AgentStates(BaseModel):
    ReportParserAgent: ReportParserState = Field(default_factory=ReportParserState)
    LedgerAuditorAgent: LedgerAuditorState = Field(default_factory=LedgerAuditorState)
    MediaSentinelAgent: MediaSentinelState = Field(default_factory=MediaSentinelState)
    GeospatialTruthAgent: GeospatialTruthState = Field(
        default_factory=GeospatialTruthState
    )


class Discrepancy(BaseModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"]
    summary: str
    claim_id: str
    ledger_row_id: str | None = None
    geo_anchor: dict[str, float] | None = None


class GlobalMetrics(BaseModel):
    weighted_risk_score: float = 0.0
    confidence_score: float = 0.0
    final_verdict: FinalVerdict = "CLEAR"
    executive_summary: str = ""
    agent_weights: dict[str, float] = Field(default_factory=dict)


class AuditPayload(BaseModel):
    audit_id: str
    meta: AuditMeta
    agent_states: AgentStates = Field(default_factory=AgentStates)
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    global_metrics: GlobalMetrics = Field(default_factory=GlobalMetrics)


class AuditStreamEvent(BaseModel):
    type: Literal["agent_update", "global_update", "complete", "error"]
    agent: AgentKey | None = None
    payload: AuditPayload
    message: str | None = None
