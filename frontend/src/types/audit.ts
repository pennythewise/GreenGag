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

export type EsgPillar = 'environment' | 'social' | 'governance';

export interface ExtractedClaim {
  id: string;
  label: string;
  raw_text: string;
  pillar?: EsgPillar;
  category?: string;
  claim_type?: string;
  entity?: string;
  metric?: string;
  target_value?: string;
  achieved_value?: string;
  baseline_value?: string;
  time_period?: string;
  location?: string;
  unit?: string;
  page?: number;
  section_heading?: string;
  key_metrics?: Record<string, string | number | boolean | null>;
  confidence?: number;
  claimed_reduction_pct?: number;
  material_class?: string;
  stated_spend_usd?: number;
  highlight?: HighlightBox;
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
  document?: {
    title: string;
    pages: PdfPage[];
  } | null;
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

/* ── Weighted Confidence Verification ─────────────────────────────────── */

export type EvidenceLayerKey =
  | 'official_report'
  | 'financial_statements'
  | 'historical_consistency'
  | 'methodology'
  | 'industry_benchmark';

/** One row in the GHG intensity comparison table (industry_benchmark layer only). */
export interface PeerIntensityRow {
  company: string;
  revenue_rm_million: number | null;
  scope_1_2_tco2e: number | null;
  scope_3_tco2e: number | null;
  total_scope_123_tco2e: number | null;
  intensity_scope_12_per_rm_million: number | null;
  intensity_scope_3_per_rm_million: number | null;
  intensity_total_per_rm_million: number | null;
  /** Alias for scope 1+2 intensity (backward compatible). */
  intensity_tco2e_per_rm_million: number | null;
  data_year: string | null;
  data_found: boolean;
  source: string;
  /** True for the company being audited; false for peer companies. */
  is_target: boolean;
}

export interface EvidenceLayerScore {
  layer_key: EvidenceLayerKey;
  label: string;
  weight: number;
  score: number;
  weighted_score: number;
  evidence_snippets: string[];
  sources: string[];
  rationale: string;
  missing_evidence: boolean;
  contradiction: boolean;
  /** GHG intensity comparison table — populated for industry_benchmark layer when live search ran. */
  peer_table?: PeerIntensityRow[];
  /** One-line TLDR for auditors. */
  benchmark_tldr?: string | null;
  /** AI-generated insights paragraph from sustainability report comparison. */
  benchmark_insights?: string | null;
  /** One-sentence verdict on claim credibility. */
  benchmark_conclusion?: string | null;
  /** Standard unit used for comparison, e.g. "tCO₂e / RM million revenue". */
  benchmark_unit?: string | null;
  /** Observed peer intensity range across FY2023–FY2025. */
  peer_intensity_range?: string | null;
}

export interface WeightedVerificationResult {
  id: string;
  document_id: string;
  claim_id: string;
  overall_score: number;
  uncapped_score?: number | null;
  contradiction_flag: boolean;
  score_cap_applied: boolean;
  score_cap_reason?: string | null;
  layer_scores: EvidenceLayerScore[];
  rationale_trail: string[];
  mode: 'mock' | 'live';
  created_at?: string | null;
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

export interface GeospatialTruthState extends BaseAgentState {
  metrics: {
    satellite_source: string;
    observed_gas_variance_percentage: number;
    confidence_index: number;
    /** Absolute veto power — overrides the verdict when true. */
    veto: boolean;
  };
  unit: string;
  time_series: TimeSeriesPoint[];
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
