/**
 * Canonical audit-state contract.
 *
 * Mirrors backend/models/schemas.py exactly. Both the mock fixture and the live
 * FastAPI stream conform to AuditPayload — every component reads only from here.
 *
 * Status enum follows CLAUDE.md (IDLE | PROCESSING | SUCCESS | ALERT). The PRD
 * sample payload's "COMPLETED" maps to SUCCESS.
 */

export type AgentStatus = 'IDLE' | 'PROCESSING' | 'SUCCESS' | 'ALERT';

export type FinalVerdict =
  | 'CLEAR'
  | 'LOW_RISK'
  | 'MODERATE_RISK'
  | 'HIGH_RISK'
  | 'CRITICAL_RISK_FRAUD_DETECTED';

export type AgentKey =
  | 'ReportParserAgent'
  | 'LedgerAuditorAgent'
  | 'MediaSentinelAgent'
  | 'GeospatialTruthAgent';

export interface GeoPolygon {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface AuditMeta {
  target_entity: string;
  project_name: string;
  coordinates: GeoPolygon;
}

export interface BaseAgentState {
  status: AgentStatus;
  /** 0.0–1.0 contribution to the weighted index. */
  risk_contribution: number;
  /** Step-by-step XAI reasoning rendered in the agent thought log. */
  rationale_trail: string[];
  /** Tool currently attached to the agent (shown on the swimlane card). */
  active_tool?: string;
  /** 0.0–1.0 execution progress for the card's progress ring. */
  progress: number;
}

/* ── Agent 2: Report Parser ───────────────────────────────────────────── */

/** Normalized bounding box on a PDF page, expressed in 0–100 page-percent. */
export interface HighlightBox {
  page: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ExtractedClaim {
  id: string;
  label: string;
  raw_text: string;
  claimed_reduction_pct?: number;
  material_class?: string;
  stated_spend_usd?: number;
  highlight: HighlightBox;
}

export interface PdfBlock {
  id: string;
  text: string;
  /** When set, this block is a highlighted claim source. */
  claim_id?: string;
}

export interface PdfPage {
  page: number;
  heading: string;
  blocks: PdfBlock[];
}

export interface ReportParserState extends BaseAgentState {
  document: {
    title: string;
    pages: PdfPage[];
  };
  extracted_claims: ExtractedClaim[];
}

/* ── Agent 3: Ledger Auditor ──────────────────────────────────────────── */

export interface LedgerRow {
  id: string;
  date: string;
  invoice_id: string;
  vendor: string;
  material: string;
  category: 'green' | 'standard';
  amount_usd: number;
  flagged: boolean;
  /** Links the row to a PDF claim for the Discrepancy Canvas SVG connector. */
  linked_claim_id?: string;
  note?: string;
}

export interface LedgerAuditorState extends BaseAgentState {
  extracted_metrics: {
    verified_green_spend_usd: number;
    unverified_standard_spend_usd: number;
    green_ratio: number;
  };
  rows: LedgerRow[];
}

/* ── Agent 4: Media Sentinel ──────────────────────────────────────────── */

export interface MediaArticle {
  id: string;
  headline: string;
  source: string;
  url: string;
  published: string;
  snippet: string;
  /** 0.0–1.0 reputational contradiction score. */
  contradiction_score: number;
  tag: 'incident' | 'ngo' | 'community' | 'news';
}

export interface MediaSentinelState extends BaseAgentState {
  articles: MediaArticle[];
}

/* ── Agent 5: Geospatial Truth ────────────────────────────────────────── */

export interface TimeSeriesPoint {
  date: string;
  /** Company's claimed emissions index (the declining promise). */
  claimed: number;
  /** Satellite-observed value (the flatline reality). */
  observed: number;
}

export interface HeatPixel {
  lng: number;
  lat: number;
  /** 0.0–1.0 normalized gas column density. */
  intensity: number;
}

/** One satellite data source — e.g. Sentinel-5P NO₂, ERA5 wind, Planet NDVI. */
export interface SatelliteLayer {
  layer_id: string;
  source: string;
  parameter: string;
  unit: string;
  observed_variance_pct: number;
  confidence_index: number;
  anomaly_detected: boolean;
  /** True when this layer's physical evidence contradicts the corporate claim. */
  veto: boolean;
}

/** Claimed vs. observed time series for one satellite layer. */
export interface LayerTimeSeries {
  layer_id: string;
  label: string;
  unit: string;
  points: TimeSeriesPoint[];
}

export interface GeoMetrics {
  layers: SatelliteLayer[];
  plume_trajectory_modeled: boolean;
  asset_geofenced: boolean;
  /** True if any layer asserts a veto. */
  veto: boolean;
}

export interface GeospatialTruthState extends BaseAgentState {
  metrics: GeoMetrics;
  /** One time-series per satellite layer (claimed vs. observed). */
  layer_series: LayerTimeSeries[];
  heatmap: HeatPixel[];
}

/* ── Aggregate ────────────────────────────────────────────────────────── */

export interface AgentStates {
  ReportParserAgent: ReportParserState;
  LedgerAuditorAgent: LedgerAuditorState;
  MediaSentinelAgent: MediaSentinelState;
  GeospatialTruthAgent: GeospatialTruthState;
}

export type DiscrepancySeverity = 'low' | 'medium' | 'high' | 'critical';

/** A triangulated contradiction surfaced on the Discrepancy Canvas. */
export interface Discrepancy {
  id: string;
  severity: DiscrepancySeverity;
  summary: string;
  claim_id: string;
  ledger_row_id?: string;
  /** Optional anchor into the geospatial evidence. */
  geo_anchor?: { lng: number; lat: number };
}

export interface GlobalMetrics {
  weighted_risk_score: number;
  confidence_score: number;
  final_verdict: FinalVerdict;
  executive_summary: string;
  /** Per-agent weights applied to the Weighted Integrity Index. */
  agent_weights: Record<AgentKey, number>;
}

export interface AuditPayload {
  audit_id: string;
  meta: AuditMeta;
  agent_states: AgentStates;
  discrepancies: Discrepancy[];
  global_metrics: GlobalMetrics;
}

/** Server-sent event envelope for live agent transitions. */
export interface AuditStreamEvent {
  type: 'agent_update' | 'global_update' | 'complete' | 'error';
  agent?: AgentKey;
  payload: AuditPayload;
  message?: string;
}
