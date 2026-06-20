"""Deterministic fixtures for GREENGAG_DATA_MODE=mock.

Three audit scenarios are available:
  kl_central_audit_payload()   — KL Central Eco-Tower (default demo)
  sunway_quarry_audit_payload() — Sunway Quarry, Rawang (GHG cross-check)
  ulu_muda_audit_payload()      — Ulu Muda Reforestation, Kedah (NDVI)
"""

from __future__ import annotations

import math

from models.schemas import (
    AuditMeta,
    AuditPayload,
    Discrepancy,
    ExtractedClaim,
    GeoMetrics,
    GeoPolygon,
    GeospatialTruthState,
    GlobalMetrics,
    AgentStates,
    HeatPixel,
    HighlightBox,
    LayerTimeSeries,
    LedgerAuditorState,
    LedgerMetrics,
    LedgerRow,
    MediaArticle,
    MediaSentinelState,
    PdfBlock,
    PdfDocument,
    PdfPage,
    ReportParserState,
    SatelliteLayer,
    TimeSeriesPoint,
)

# Per-agent weights for the Weighted Integrity Index (geospatial = 50%).
AGENT_WEIGHTS: dict[str, float] = {
    "GeospatialTruthAgent": 0.50,
    "LedgerAuditorAgent": 0.25,
    "MediaSentinelAgent": 0.15,
    "ReportParserAgent": 0.10,
}


# ── Shared helpers ─────────────────────────────────────────────────────────


def _heatmap(min_lng: float, min_lat: float, step: float = 0.0008) -> list[HeatPixel]:
    pixels: list[HeatPixel] = []
    for i in range(5):
        for j in range(5):
            dx, dy = i - 2, j - 2
            dist = math.sqrt(dx * dx + dy * dy)
            intensity = max(0.0, 1 - dist / 3) ** 1.5
            pixels.append(
                HeatPixel(
                    lng=min_lng + i * step,
                    lat=min_lat + j * step,
                    intensity=round(intensity, 2),
                )
            )
    return pixels


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO A — KL Central Eco-Tower (default demo)
# ═══════════════════════════════════════════════════════════════════════════

_KL_META = AuditMeta(
    target_entity="Malaya BuildCorp Group",
    project_name="KL Central Eco-Tower Expansion",
    coordinates=GeoPolygon(
        coordinates=[
            [
                [101.686, 3.139],
                [101.690, 3.139],
                [101.690, 3.143],
                [101.686, 3.143],
                [101.686, 3.139],
            ]
        ]
    ),
)


def _kl_report_parser_state() -> ReportParserState:
    return ReportParserState(
        status="SUCCESS",
        risk_contribution=0.10,
        progress=1.0,
        active_tool="pdf_extractor::claude-opus-4-8",
        rationale_trail=[
            'Loaded ESG report "2025 Sustainability & Net-Zero Pathway" (48 pages).',
            "Stripped promotional cover, foreword, and 11 stock-photo pages.",
            "Parsed PDF structure lines 112-140 for measurable commitments.",
            "Identified explicit emission-reduction commitment clause (30% by 2026).",
            "Extracted material classification + self-reported green budget.",
            "Normalized 3 claims into structured JSON for downstream agents.",
        ],
        document=PdfDocument(
            title="2025 Sustainability & Net-Zero Pathway",
            pages=[
                PdfPage(
                    page=4,
                    heading="Our Decarbonization Commitment",
                    blocks=[
                        PdfBlock(
                            id="b1",
                            text="Malaya BuildCorp is proud to lead the region toward a regenerative built environment.",
                        ),
                        PdfBlock(
                            id="b2",
                            text="We commit to a 30% reduction in operational carbon intensity across the KL Central Eco-Tower Expansion by year-end 2026.",
                            claim_id="c-reduction",
                        ),
                        PdfBlock(
                            id="b3",
                            text="Every structural pour on this flagship project uses Cemex Vertua low-carbon concrete, sourced exclusively from certified green suppliers.",
                            claim_id="c-material",
                        ),
                    ],
                ),
                PdfPage(
                    page=12,
                    heading="Green Capital Allocation",
                    blocks=[
                        PdfBlock(
                            id="b4",
                            text="A dedicated sustainability budget of USD 1.2 million has been ring-fenced for verified low-carbon materials procurement on this project.",
                            claim_id="c-spend",
                        ),
                        PdfBlock(
                            id="b5",
                            text="We recorded zero environmental incidents at the construction site during the reporting period.",
                            claim_id="c-incidents",
                        ),
                    ],
                ),
            ],
        ),
        extracted_claims=[
            ExtractedClaim(
                id="c-reduction",
                label="Carbon reduction commitment",
                raw_text="30% reduction in operational carbon intensity by year-end 2026",
                claimed_reduction_pct=30,
                highlight=HighlightBox(page=4, x=8, y=41, w=84, h=9),
            ),
            ExtractedClaim(
                id="c-material",
                label="Material classification",
                raw_text="Cemex Vertua low-carbon concrete, certified green suppliers",
                material_class="Cemex Vertua Low-Carbon Concrete",
                highlight=HighlightBox(page=4, x=8, y=55, w=84, h=9),
            ),
            ExtractedClaim(
                id="c-spend",
                label="Self-reported green spend",
                raw_text="USD 1.2 million ring-fenced for verified low-carbon materials",
                stated_spend_usd=1_200_000,
                highlight=HighlightBox(page=12, x=8, y=30, w=84, h=8),
            ),
            ExtractedClaim(
                id="c-incidents",
                label="Zero-incident claim",
                raw_text="zero environmental incidents at the construction site",
                highlight=HighlightBox(page=12, x=8, y=47, w=84, h=8),
            ),
        ],
    )


def _kl_ledger_auditor_state() -> LedgerAuditorState:
    return LedgerAuditorState(
        status="ALERT",
        risk_contribution=0.85,
        progress=1.0,
        active_tool="ledger_query::postgres(internal)",
        rationale_trail=[
            "Connected to internal procurement ledger (read-only).",
            "Pulled 142 purchase orders tagged to project KL-CENTRAL-EXP.",
            "Cross-referenced vendor index against approved green-material provider lists.",
            "Verified green spend totals USD 180,000 — only 15% of the claimed 1.2M budget.",
            "Detected standard cement-grade purchase-order swap on invoice #INV-9981.",
            "Bait-and-switch pattern: 85% of spend routed to high-carbon suppliers.",
        ],
        extracted_metrics=LedgerMetrics(
            verified_green_spend_usd=180_000,
            unverified_standard_spend_usd=1_020_000,
            green_ratio=0.15,
        ),
        rows=[
            LedgerRow(id="l1", date="2025-08-02", invoice_id="INV-9712",
                      vendor="Cemex Vertua (Certified)", material="Vertua Low-Carbon Concrete",
                      category="green", amount_usd=120_000, flagged=False),
            LedgerRow(id="l2", date="2025-09-15", invoice_id="INV-9844",
                      vendor="Greenform Rebar Co.", material="Recycled Structural Steel",
                      category="green", amount_usd=60_000, flagged=False),
            LedgerRow(id="l3", date="2025-10-28", invoice_id="INV-9981",
                      vendor="Klang Standard Cement Sdn Bhd", material="OPC Grade 42.5 (high-carbon)",
                      category="standard", amount_usd=540_000, flagged=True,
                      linked_claim_id="c-material",
                      note="PO swapped from Vertua to standard OPC — contradicts material claim."),
            LedgerRow(id="l4", date="2025-12-11", invoice_id="INV-10233",
                      vendor="Klang Standard Cement Sdn Bhd", material="OPC Grade 42.5 (high-carbon)",
                      category="standard", amount_usd=300_000, flagged=True,
                      linked_claim_id="c-spend",
                      note="Charged against the green budget line but non-certified material."),
            LedgerRow(id="l5", date="2026-02-03", invoice_id="INV-10588",
                      vendor="PerakAggregate Holdings", material="Standard Aggregate Mix",
                      category="standard", amount_usd=180_000, flagged=True,
                      linked_claim_id="c-spend", note="Not on approved green provider list."),
        ],
    )


def _kl_media_sentinel_state() -> MediaSentinelState:
    return MediaSentinelState(
        status="ALERT",
        risk_contribution=0.70,
        progress=1.0,
        active_tool="web_scraper::nlp-classifier",
        rationale_trail=[
            "Scraped 1,204 documents across news, NGO databases, and community boards.",
            "Ran NLP contradiction classifier against extracted corporate claims.",
            'Surfaced 3 high-signal contradictions to the "zero incidents" claim.',
            "Greenpeace SEA flagged an unreported slurry discharge in Nov 2025.",
            "Local board reports match the satellite anomaly window.",
        ],
        articles=[
            MediaArticle(id="m1", headline="Residents report grey slurry runoff near KL Central tower site",
                         source="Klang Valley Community Board", url="https://example.org/community/klang-slurry",
                         published="2025-11-09",
                         snippet="Multiple residents posted photos of grey discharge entering the storm drain adjacent to the Eco-Tower construction site over the weekend.",
                         contradiction_score=0.82, tag="community"),
            MediaArticle(id="m2", headline='Greenpeace SEA logs unreported discharge at "eco" megaproject',
                         source="Greenpeace Southeast Asia", url="https://example.org/ngo/greenpeace-discharge",
                         published="2025-11-21",
                         snippet="Field monitors recorded an industrial slurry discharge that does not appear in the developer's self-reported incident log.",
                         contradiction_score=0.91, tag="ngo"),
            MediaArticle(id="m3", headline='BuildCorp touts "zero-incident" record amid scrutiny',
                         source="The Malayan Ledger", url="https://example.org/news/buildcorp-zero-incident",
                         published="2026-01-14",
                         snippet="The developer reiterated a flawless environmental record this week, even as regulators confirmed an open inquiry into a November discharge.",
                         contradiction_score=0.76, tag="news"),
            MediaArticle(id="m4", headline="Quarterly air-quality readings steady near industrial KL belt",
                         source="Regional Environment Wire", url="https://example.org/news/air-quality-steady",
                         published="2026-03-02",
                         snippet="Ambient monitoring stations show no measurable improvement in NO2 levels across the central construction corridor.",
                         contradiction_score=0.58, tag="news"),
        ],
    )


def _kl_geospatial_truth_state() -> GeospatialTruthState:
    no2_points = [
        ("2025-06", 100, 100), ("2025-07", 96, 101), ("2025-08", 92, 99),
        ("2025-09", 87, 102), ("2025-10", 83, 100), ("2025-11", 79, 103),
        ("2025-12", 75, 101), ("2026-01", 72, 104), ("2026-02", 70, 100),
        ("2026-03", 70, 102), ("2026-04", 70, 105), ("2026-05", 70, 103),
    ]
    weather_points = [
        ("2025-06", 12, 14), ("2025-07", 11, 13), ("2025-08", 13, 15),
        ("2025-09", 12, 14), ("2025-10", 10, 12), ("2025-11", 11, 16),
        ("2025-12", 14, 17), ("2026-01", 13, 15), ("2026-02", 12, 14),
        ("2026-03", 11, 13), ("2026-04", 12, 15), ("2026-05", 13, 16),
    ]
    return GeospatialTruthState(
        status="ALERT",
        risk_contribution=0.95,
        progress=1.0,
        active_tool="sentinel5p::tropomi-no2 | ecmwf::era5-wind",
        rationale_trail=[
            "Ingested Sentinel-5P L2 NetCDF for NO2 over polygon (12 months).",
            "Ingested ECMWF ERA5 GRIB for surface wind speed over same AOI.",
            "Applied xarray spatial crop and polygon masking to both datasets.",
            "Ran NOAA HYSPLIT plume back-trajectory — wind confirms local source attribution.",
            "GeoPandas asset geofencing: NO2 anomaly centroid intersects quarry permit boundary.",
            "Anomalous Gas Core Identification: NO2 reading 40% above baseline, exceeds 2σ threshold.",
            "VETO ASSERTED: physical evidence contradicts the 30% carbon reduction claim.",
        ],
        metrics=GeoMetrics(
            layers=[
                SatelliteLayer(
                    layer_id="no2",
                    source="Sentinel-5P_TROPOMI",
                    parameter="NO2",
                    unit="µmol/m² (tropospheric column)",
                    observed_variance_pct=0.40,
                    confidence_index=0.92,
                    anomaly_detected=True,
                    veto=True,
                ),
                SatelliteLayer(
                    layer_id="weather",
                    source="ECMWF_ERA5",
                    parameter="Wind Speed",
                    unit="m/s (10m surface)",
                    observed_variance_pct=0.12,
                    confidence_index=0.88,
                    anomaly_detected=False,
                    veto=False,
                ),
            ],
            plume_trajectory_modeled=True,
            asset_geofenced=True,
            veto=True,
        ),
        layer_series=[
            LayerTimeSeries(
                layer_id="no2",
                label="NO2 Tropospheric Column",
                unit="µmol/m² (normalized index)",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in no2_points],
            ),
            LayerTimeSeries(
                layer_id="weather",
                label="Surface Wind Speed",
                unit="m/s",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in weather_points],
            ),
        ],
        heatmap=_heatmap(101.686, 3.139),
    )


_KL_DISCREPANCIES = [
    Discrepancy(id="d1", severity="critical",
                summary="Report claims exclusive Vertua low-carbon concrete, but invoice #INV-9981 shows a USD 540K standard OPC purchase.",
                claim_id="c-material", ledger_row_id="l3"),
    Discrepancy(id="d2", severity="high",
                summary='USD 1.2M "green budget" claim contradicted by USD 480K routed to non-certified suppliers.',
                claim_id="c-spend", ledger_row_id="l4"),
    Discrepancy(id="d3", severity="critical",
                summary="Claimed 30% emissions reduction; Sentinel-5P shows a +40% NO2 variance flatline over the target polygon.",
                claim_id="c-reduction", geo_anchor={"lng": 101.6884, "lat": 3.1414}),
    Discrepancy(id="d4", severity="high",
                summary='"Zero environmental incidents" contradicted by an NGO-logged November slurry discharge.',
                claim_id="c-incidents"),
]


def kl_central_audit_payload() -> AuditPayload:
    return AuditPayload(
        audit_id="aud_2026_98x11",
        meta=_KL_META,
        agent_states=AgentStates(
            ReportParserAgent=_kl_report_parser_state(),
            LedgerAuditorAgent=_kl_ledger_auditor_state(),
            MediaSentinelAgent=_kl_media_sentinel_state(),
            GeospatialTruthAgent=_kl_geospatial_truth_state(),
        ),
        discrepancies=_KL_DISCREPANCIES,
        global_metrics=GlobalMetrics(
            weighted_risk_score=0.87,
            confidence_score=0.91,
            final_verdict="CRITICAL_RISK_FRAUD_DETECTED",
            executive_summary=(
                "GeospatialTruthAgent asserts veto: Sentinel-5P NO2 data over the KL Central polygon "
                "shows a +40% emission variance against a claimed 30% reduction. Ledger audit confirms "
                "85% of the green budget was misclassified. Physical evidence overrides all corporate claims."
            ),
            agent_weights=AGENT_WEIGHTS,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO B — Sunway Quarry, Rawang (GHG multi-gas cross-check)
# ═══════════════════════════════════════════════════════════════════════════
# Sunway Quarry operates a limestone quarrying and concrete batching operation
# near Rawang, Selangor (~3.33°N, 101.57°E). The ESG report claims a "dust
# suppression and GHG reduction program" cut particulate and methane emissions
# by 25%. Satellite layering reveals a CH4 spike and sustained NO2 elevation.

_SQ_META = AuditMeta(
    target_entity="Sunway Quarry Sdn Bhd",
    project_name="Rawang Limestone Quarry Operations",
    coordinates=GeoPolygon(
        coordinates=[
            [
                [101.565, 3.325],
                [101.575, 3.325],
                [101.575, 3.335],
                [101.565, 3.335],
                [101.565, 3.325],
            ]
        ]
    ),
)


def _sq_report_parser_state() -> ReportParserState:
    return ReportParserState(
        status="SUCCESS",
        risk_contribution=0.10,
        progress=1.0,
        active_tool="pdf_extractor::claude-opus-4-8",
        rationale_trail=[
            'Loaded ESG report "Sunway Quarry 2025 Environmental Stewardship Report" (32 pages).',
            "Identified GHG reduction commitment: 25% cut in CH4 and particulate by Q4 2025.",
            "Extracted dust suppression programme budget claim: MYR 2.4 million allocated.",
            "Identified zero-incident claim for blasting operations during reporting period.",
            "Normalized 3 claims into structured JSON.",
        ],
        document=PdfDocument(
            title="Sunway Quarry 2025 Environmental Stewardship Report",
            pages=[
                PdfPage(
                    page=3,
                    heading="GHG Reduction Commitment",
                    blocks=[
                        PdfBlock(
                            id="sq-b1",
                            text="Our dust suppression and methane capture programme has delivered a 25% reduction in GHG and particulate intensity across Rawang operations by Q4 2025.",
                            claim_id="sq-ghg",
                        ),
                    ],
                ),
                PdfPage(
                    page=9,
                    heading="Environmental Capital Allocation",
                    blocks=[
                        PdfBlock(
                            id="sq-b2",
                            text="MYR 2.4 million has been ring-fenced for certified dust suppression equipment and methane capture infrastructure.",
                            claim_id="sq-spend",
                        ),
                        PdfBlock(
                            id="sq-b3",
                            text="Zero blasting incidents recorded in 2025. Air quality monitors showed consistent improvement.",
                            claim_id="sq-incidents",
                        ),
                    ],
                ),
            ],
        ),
        extracted_claims=[
            ExtractedClaim(
                id="sq-ghg",
                label="GHG reduction commitment",
                raw_text="25% reduction in GHG and particulate intensity by Q4 2025",
                claimed_reduction_pct=25,
                highlight=HighlightBox(page=3, x=8, y=38, w=84, h=10),
            ),
            ExtractedClaim(
                id="sq-spend",
                label="Environmental capex",
                raw_text="MYR 2.4 million ring-fenced for dust suppression and CH4 capture",
                stated_spend_usd=533_000,
                highlight=HighlightBox(page=9, x=8, y=30, w=84, h=8),
            ),
            ExtractedClaim(
                id="sq-incidents",
                label="Zero-incident claim",
                raw_text="Zero blasting incidents in 2025; consistent air quality improvement",
                highlight=HighlightBox(page=9, x=8, y=47, w=84, h=8),
            ),
        ],
    )


def _sq_ledger_auditor_state() -> LedgerAuditorState:
    return LedgerAuditorState(
        status="ALERT",
        risk_contribution=0.70,
        progress=1.0,
        active_tool="ledger_query::postgres(internal)",
        rationale_trail=[
            "Pulled 87 purchase orders tagged to Rawang quarry environmental programme.",
            "MYR 2.4M claim: only MYR 310K traced to certified dust suppression equipment.",
            "MYR 2.09M routed to general plant maintenance — not certified GHG-reduction spend.",
            "No methane capture infrastructure purchase orders found.",
        ],
        extracted_metrics=LedgerMetrics(
            verified_green_spend_usd=69_000,
            unverified_standard_spend_usd=464_000,
            green_ratio=0.13,
        ),
        rows=[
            LedgerRow(id="sq-l1", date="2025-07-10", invoice_id="SQ-INV-0441",
                      vendor="Enviro-Tech Dust Suppression Sdn Bhd", material="Certified dust cannon units",
                      category="green", amount_usd=69_000, flagged=False),
            LedgerRow(id="sq-l2", date="2025-09-22", invoice_id="SQ-INV-0509",
                      vendor="Rawang Plant Services", material="General conveyor maintenance",
                      category="standard", amount_usd=210_000, flagged=True,
                      linked_claim_id="sq-spend",
                      note="Charged to GHG programme budget line — no certified environmental benefit."),
            LedgerRow(id="sq-l3", date="2025-11-05", invoice_id="SQ-INV-0571",
                      vendor="Rawang Plant Services", material="Crusher overhaul",
                      category="standard", amount_usd=254_000, flagged=True,
                      linked_claim_id="sq-spend",
                      note="No methane capture component — contradicts CH4 reduction claim."),
        ],
    )


def _sq_media_sentinel_state() -> MediaSentinelState:
    return MediaSentinelState(
        status="ALERT",
        risk_contribution=0.65,
        progress=1.0,
        active_tool="web_scraper::nlp-classifier",
        rationale_trail=[
            "Scraped 643 documents across news, DOE filings, and Rawang community boards.",
            "DOE Selangor complaint log: 4 dust/smoke incidents at Rawang quarry Q3–Q4 2025.",
            "Resident reports of persistent haze during blasting corroborate satellite CH4 spike.",
        ],
        articles=[
            MediaArticle(id="sq-m1", headline="Rawang residents file DOE complaints over quarry dust haze",
                         source="Selangor DOE Community Portal", url="https://example.org/doe/rawang-complaints",
                         published="2025-10-14",
                         snippet="Four formal complaints lodged by Taman Rawang Perdana residents citing thick dust and chemical odour linked to Sunway Quarry blasting operations.",
                         contradiction_score=0.88, tag="community"),
            MediaArticle(id="sq-m2", headline="Selangor air quality index spikes in Rawang industrial corridor",
                         source="The Star Online", url="https://example.org/news/rawang-aqi-spike",
                         published="2025-11-03",
                         snippet="PM10 readings near the Rawang quarry belt breached the 150 threshold on three separate days in October 2025.",
                         contradiction_score=0.74, tag="news"),
            MediaArticle(id="sq-m3", headline='Sunway Quarry announces "clean quarrying" certification bid',
                         source="Construction Malaysia Weekly", url="https://example.org/news/sunway-clean-quarry",
                         published="2025-12-18",
                         snippet="Company touts zero-incident record even as DOE investigation into Q3 dust events remains open.",
                         contradiction_score=0.79, tag="news"),
        ],
    )


def _sq_geospatial_truth_state() -> GeospatialTruthState:
    # NO2: quarry blasting + diesel fleet exhaust
    no2_pts = [
        ("2025-Q1", 100, 98), ("2025-Q2", 95, 101), ("2025-Q3", 90, 108), ("2025-Q4", 75, 112),
    ]
    # CH4: methane from limestone decomposition + fuel combustion during blasting
    ch4_pts = [
        ("2025-Q1", 100, 97), ("2025-Q2", 96, 104), ("2025-Q3", 92, 119), ("2025-Q4", 75, 131),
    ]
    # ERA5 wind: southwesterly monsoon funnels plume toward residential areas
    wind_pts = [
        ("2025-Q1", 8, 9), ("2025-Q2", 9, 11), ("2025-Q3", 10, 13), ("2025-Q4", 8, 10),
    ]
    return GeospatialTruthState(
        status="ALERT",
        risk_contribution=0.95,
        progress=1.0,
        active_tool="sentinel5p::tropomi-no2-ch4 | ecmwf::era5-wind",
        rationale_trail=[
            "Ingested Sentinel-5P L2 NetCDF for NO2 and CH4 over Rawang polygon (4 quarters).",
            "Ingested ECMWF ERA5 GRIB for surface wind speed and direction over same AOI.",
            "Applied xarray spatial crop and masking — polygon aligned to quarry permit boundary.",
            "NOAA HYSPLIT back-trajectory: SW monsoon wind confirms plume source is quarry site.",
            "GeoPandas intersect: both NO2 and CH4 anomaly centroids fall within quarry asset boundary.",
            "NO2 anomaly: Q4 observed 112 vs claimed 75 (index) — +49% above reduction target.",
            "CH4 anomaly: Q4 observed 131 vs claimed 75 — +75% spike, consistent with blasting VOC release.",
            "VETO ASSERTED: two independent GHG layers contradict the 25% reduction claim.",
        ],
        metrics=GeoMetrics(
            layers=[
                SatelliteLayer(
                    layer_id="no2",
                    source="Sentinel-5P_TROPOMI",
                    parameter="NO2",
                    unit="µmol/m² (tropospheric column)",
                    observed_variance_pct=0.49,
                    confidence_index=0.91,
                    anomaly_detected=True,
                    veto=True,
                ),
                SatelliteLayer(
                    layer_id="ch4",
                    source="Sentinel-5P_TROPOMI",
                    parameter="CH4",
                    unit="ppb (dry-air mole fraction)",
                    observed_variance_pct=0.75,
                    confidence_index=0.87,
                    anomaly_detected=True,
                    veto=True,
                ),
                SatelliteLayer(
                    layer_id="weather",
                    source="ECMWF_ERA5",
                    parameter="Wind Speed",
                    unit="m/s (10m surface)",
                    observed_variance_pct=0.08,
                    confidence_index=0.95,
                    anomaly_detected=False,
                    veto=False,
                ),
            ],
            plume_trajectory_modeled=True,
            asset_geofenced=True,
            veto=True,
        ),
        layer_series=[
            LayerTimeSeries(
                layer_id="no2",
                label="NO2 Tropospheric Column",
                unit="µmol/m² (normalized index)",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in no2_pts],
            ),
            LayerTimeSeries(
                layer_id="ch4",
                label="CH4 Dry-Air Mole Fraction",
                unit="ppb (normalized index)",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in ch4_pts],
            ),
            LayerTimeSeries(
                layer_id="weather",
                label="Surface Wind Speed (ERA5)",
                unit="m/s",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in wind_pts],
            ),
        ],
        heatmap=_heatmap(101.565, 3.325),
    )


def sunway_quarry_audit_payload() -> AuditPayload:
    return AuditPayload(
        audit_id="aud_2026_sq_rawang",
        meta=_SQ_META,
        agent_states=AgentStates(
            ReportParserAgent=_sq_report_parser_state(),
            LedgerAuditorAgent=_sq_ledger_auditor_state(),
            MediaSentinelAgent=_sq_media_sentinel_state(),
            GeospatialTruthAgent=_sq_geospatial_truth_state(),
        ),
        discrepancies=[
            Discrepancy(id="sq-d1", severity="critical",
                        summary="Claimed 25% GHG reduction; Sentinel-5P CH4 layer shows +75% spike in Q4 2025.",
                        claim_id="sq-ghg", geo_anchor={"lng": 101.570, "lat": 3.330}),
            Discrepancy(id="sq-d2", severity="critical",
                        summary="NO2 also elevated +49% — NOAA HYSPLIT confirms quarry as plume source.",
                        claim_id="sq-ghg", geo_anchor={"lng": 101.570, "lat": 3.330}),
            Discrepancy(id="sq-d3", severity="high",
                        summary="MYR 2.4M environmental capex: only 13% (MYR 310K) traced to certified GHG-reduction spend.",
                        claim_id="sq-spend", ledger_row_id="sq-l2"),
            Discrepancy(id="sq-d4", severity="high",
                        summary='"Zero blasting incidents" contradicted by 4 DOE complaints and PM10 breaches in Q3–Q4.',
                        claim_id="sq-incidents"),
        ],
        global_metrics=GlobalMetrics(
            weighted_risk_score=0.91,
            confidence_score=0.89,
            final_verdict="CRITICAL_RISK_FRAUD_DETECTED",
            executive_summary=(
                "GeospatialTruthAgent asserts veto on two independent GHG layers: CH4 is +75% and NO2 is +49% "
                "above the claimed reduction curve over Rawang quarry. NOAA HYSPLIT back-trajectory and "
                "GeoPandas asset geofencing confirm the source. Ledger audit reveals 87% of the "
                "environmental capex cannot be traced to certified GHG-reduction activity."
            ),
            agent_weights=AGENT_WEIGHTS,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO C — Ulu Muda Reforestation, Kedah (NDVI coverage check)
# ═══════════════════════════════════════════════════════════════════════════
# Kedah Forestry Corporation claims 2,000 ha of secondary forest replanted
# in the Ulu Muda catchment (~5.8°N, 100.9°E) since 2023. Planet Labs NDVI
# time-series shows canopy recovery on only ~600 ha — a 70% shortfall.

_UM_META = AuditMeta(
    target_entity="Kedah Forestry Corporation",
    project_name="Ulu Muda Carbon Sink Reforestation",
    coordinates=GeoPolygon(
        coordinates=[
            [
                [100.880, 5.790],
                [100.920, 5.790],
                [100.920, 5.820],
                [100.880, 5.820],
                [100.880, 5.790],
            ]
        ]
    ),
)


def _um_report_parser_state() -> ReportParserState:
    return ReportParserState(
        status="SUCCESS",
        risk_contribution=0.10,
        progress=1.0,
        active_tool="pdf_extractor::claude-opus-4-8",
        rationale_trail=[
            'Loaded ESG report "Kedah Forestry Corp — Ulu Muda Carbon Sink Prospectus 2025" (56 pages).',
            "Identified reforestation area claim: 2,000 ha replanted with native dipterocarp species.",
            "Extracted carbon sequestration projection: 48,000 tCO₂e per year by 2028.",
            "Found MYR 8.2M green bond proceeds allocated to planting operations.",
            "Normalized 3 claims into structured JSON.",
        ],
        document=PdfDocument(
            title="Ulu Muda Carbon Sink Prospectus 2025",
            pages=[
                PdfPage(
                    page=5,
                    heading="Reforestation Scope & Commitment",
                    blocks=[
                        PdfBlock(
                            id="um-b1",
                            text="As of December 2025, Kedah Forestry Corporation has successfully replanted 2,000 hectares of degraded secondary forest in the Ulu Muda catchment with native dipterocarp species.",
                            claim_id="um-area",
                        ),
                        PdfBlock(
                            id="um-b2",
                            text="The project is projected to sequester 48,000 tCO₂e per annum at full canopy maturity by 2028.",
                            claim_id="um-seq",
                        ),
                    ],
                ),
                PdfPage(
                    page=14,
                    heading="Green Bond Capital Deployment",
                    blocks=[
                        PdfBlock(
                            id="um-b3",
                            text="MYR 8.2 million from the 2024 green bond issuance has been fully deployed to seedling procurement, planting labour, and nursery establishment.",
                            claim_id="um-spend",
                        ),
                    ],
                ),
            ],
        ),
        extracted_claims=[
            ExtractedClaim(
                id="um-area",
                label="Reforestation area",
                raw_text="2,000 hectares of degraded secondary forest replanted",
                claimed_reduction_pct=None,
                highlight=HighlightBox(page=5, x=8, y=35, w=84, h=10),
            ),
            ExtractedClaim(
                id="um-seq",
                label="Carbon sequestration projection",
                raw_text="48,000 tCO₂e per annum at full canopy maturity by 2028",
                highlight=HighlightBox(page=5, x=8, y=52, w=84, h=8),
            ),
            ExtractedClaim(
                id="um-spend",
                label="Green bond deployment",
                raw_text="MYR 8.2 million fully deployed to planting operations",
                stated_spend_usd=1_755_000,
                highlight=HighlightBox(page=14, x=8, y=30, w=84, h=8),
            ),
        ],
    )


def _um_ledger_auditor_state() -> LedgerAuditorState:
    return LedgerAuditorState(
        status="ALERT",
        risk_contribution=0.60,
        progress=1.0,
        active_tool="ledger_query::postgres(internal)",
        rationale_trail=[
            "Pulled green bond disbursement ledger for Ulu Muda project.",
            "MYR 8.2M claimed: MYR 3.1M traced to nursery/seedling/labour — plausible for ~600 ha.",
            "MYR 5.1M allocated to 'land access and infrastructure' — no direct planting activity.",
            "Seedling procurement invoices support ~620 ha at standard dipterocarp density (1,250 stems/ha).",
        ],
        extracted_metrics=LedgerMetrics(
            verified_green_spend_usd=663_000,
            unverified_standard_spend_usd=1_092_000,
            green_ratio=0.38,
        ),
        rows=[
            LedgerRow(id="um-l1", date="2024-03-10", invoice_id="UM-INV-0101",
                      vendor="Benih Hijau Nursery Sdn Bhd", material="Dipterocarp seedlings (775,000 units)",
                      category="green", amount_usd=430_000, flagged=False,
                      note="Supports ~620 ha at 1,250 stems/ha — not 2,000 ha as claimed."),
            LedgerRow(id="um-l2", date="2024-06-20", invoice_id="UM-INV-0188",
                      vendor="Kedah Land Access Holdings", material="Access road & buffer zone construction",
                      category="standard", amount_usd=820_000, flagged=True,
                      linked_claim_id="um-spend",
                      note="Infrastructure spend misclassified as planting capex in green bond report."),
            LedgerRow(id="um-l3", date="2025-01-15", invoice_id="UM-INV-0304",
                      vendor="Benih Hijau Nursery Sdn Bhd", material="Replacement seedlings (top-up)",
                      category="green", amount_usd=233_000, flagged=False),
            LedgerRow(id="um-l4", date="2025-08-09", invoice_id="UM-INV-0412",
                      vendor="Kedah Land Access Holdings", material="Campsite and ranger station build",
                      category="standard", amount_usd=272_000, flagged=True,
                      linked_claim_id="um-spend",
                      note="Facility construction charged to reforestation budget line."),
        ],
    )


def _um_media_sentinel_state() -> MediaSentinelState:
    return MediaSentinelState(
        status="ALERT",
        risk_contribution=0.55,
        progress=1.0,
        active_tool="web_scraper::nlp-classifier",
        rationale_trail=[
            "Scraped 412 documents: forestry journals, NGO field reports, Kedah news archives.",
            "WWF-Malaysia field report (Mar 2026): ground-truth survey found active canopy on ~580 ha.",
            "Ulu Muda Watch community group documented bare patches in satellite imagery shared on social media.",
        ],
        articles=[
            MediaArticle(id="um-m1", headline="WWF-Malaysia ground survey finds Ulu Muda canopy recovery on only 580 ha",
                         source="WWF-Malaysia Field Reports", url="https://example.org/ngo/wwf-ulu-muda-survey",
                         published="2026-03-12",
                         snippet="Ground-truth transects across the claimed 2,000 ha reforestation zone found active dipterocarp canopy on approximately 580 hectares — 29% of the reported area.",
                         contradiction_score=0.94, tag="ngo"),
            MediaArticle(id="um-m2", headline="Ulu Muda green bond under scrutiny as satellite images show bare hillsides",
                         source="Malay Mail", url="https://example.org/news/ulu-muda-bond-scrutiny",
                         published="2026-04-01",
                         snippet="Investors are questioning the MYR 8.2M green bond disbursement after independent imagery showed large areas of uncovered terrain within the stated project boundary.",
                         contradiction_score=0.81, tag="news"),
        ],
    )


def _um_geospatial_truth_state() -> GeospatialTruthState:
    # NDVI: 0 = bare soil, 1 = dense closed canopy. Dipterocarp plantings reach ~0.55 NDVI at 2 years.
    # Claimed: full 2,000 ha progressing toward 0.55. Observed: only ~600 ha shows NDVI > 0.35.
    ndvi_pts = [
        ("2024-Q1", 0.12, 0.11), ("2024-Q2", 0.18, 0.16), ("2024-Q3", 0.25, 0.21),
        ("2024-Q4", 0.32, 0.24), ("2025-Q1", 0.38, 0.27), ("2025-Q2", 0.43, 0.29),
        ("2025-Q3", 0.48, 0.31), ("2025-Q4", 0.55, 0.33),
    ]
    # ERA5 rainfall: adequate precipitation rules out drought as explanation for low NDVI
    rain_pts = [
        ("2024-Q1", 220, 215), ("2024-Q2", 310, 304), ("2024-Q3", 280, 271),
        ("2024-Q4", 195, 190), ("2025-Q1", 230, 224), ("2025-Q2", 320, 315),
        ("2025-Q3", 295, 288), ("2025-Q4", 205, 198),
    ]
    return GeospatialTruthState(
        status="ALERT",
        risk_contribution=0.92,
        progress=1.0,
        active_tool="planet_labs::ndvi-psscene4band | ecmwf::era5-precipitation",
        rationale_trail=[
            "Ingested Planet Labs PSSScene 4-band imagery for Ulu Muda polygon (8 quarters, 3m resolution).",
            "Computed NDVI per pixel; applied cloud masking and canopy threshold (NDVI > 0.35 = active canopy).",
            "Ingested ECMWF ERA5 monthly precipitation over same AOI — rainfall adequate, drought ruled out.",
            "GeoPandas intersect: active canopy pixels mapped to 603 ha within permit boundary.",
            "Area with NDVI > 0.35 is 603 ha — 30% of the claimed 2,000 ha.",
            "Carbon sequestration projection scales to ~14,500 tCO₂e/yr, not 48,000 tCO₂e/yr.",
            "VETO ASSERTED: satellite-measured canopy coverage contradicts the 2,000 ha reforestation claim.",
        ],
        metrics=GeoMetrics(
            layers=[
                SatelliteLayer(
                    layer_id="ndvi",
                    source="Planet_NDVI",
                    parameter="NDVI",
                    unit="index (0–1, canopy threshold > 0.35)",
                    observed_variance_pct=0.40,
                    confidence_index=0.93,
                    anomaly_detected=True,
                    veto=True,
                ),
                SatelliteLayer(
                    layer_id="weather",
                    source="ECMWF_ERA5",
                    parameter="Precipitation",
                    unit="mm/quarter",
                    observed_variance_pct=0.03,
                    confidence_index=0.97,
                    anomaly_detected=False,
                    veto=False,
                ),
            ],
            plume_trajectory_modeled=False,
            asset_geofenced=True,
            veto=True,
        ),
        layer_series=[
            LayerTimeSeries(
                layer_id="ndvi",
                label="NDVI Canopy Coverage (area-mean)",
                unit="index (0–1)",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in ndvi_pts],
            ),
            LayerTimeSeries(
                layer_id="weather",
                label="Precipitation (ERA5)",
                unit="mm/quarter",
                points=[TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in rain_pts],
            ),
        ],
        heatmap=_heatmap(100.880, 5.790, step=0.008),
    )


def ulu_muda_audit_payload() -> AuditPayload:
    return AuditPayload(
        audit_id="aud_2026_um_kedah",
        meta=_UM_META,
        agent_states=AgentStates(
            ReportParserAgent=_um_report_parser_state(),
            LedgerAuditorAgent=_um_ledger_auditor_state(),
            MediaSentinelAgent=_um_media_sentinel_state(),
            GeospatialTruthAgent=_um_geospatial_truth_state(),
        ),
        discrepancies=[
            Discrepancy(id="um-d1", severity="critical",
                        summary="Claimed 2,000 ha reforestation; Planet Labs NDVI shows active canopy on only 603 ha (30%).",
                        claim_id="um-area", geo_anchor={"lng": 100.900, "lat": 5.805}),
            Discrepancy(id="um-d2", severity="high",
                        summary="Carbon sequestration projection of 48,000 tCO₂e/yr overstated by ~70% given actual canopy extent.",
                        claim_id="um-seq"),
            Discrepancy(id="um-d3", severity="high",
                        summary="MYR 8.2M green bond: MYR 5.1M misclassified as planting capex — actually infrastructure spend.",
                        claim_id="um-spend", ledger_row_id="um-l2"),
        ],
        global_metrics=GlobalMetrics(
            weighted_risk_score=0.82,
            confidence_score=0.93,
            final_verdict="HIGH_RISK",
            executive_summary=(
                "GeospatialTruthAgent asserts veto: Planet Labs NDVI analysis over the 4,000 ha permit "
                "boundary identifies active dipterocarp canopy on only 603 ha — 30% of the claimed 2,000 ha. "
                "ERA5 precipitation data rules out drought as a confounding factor. Ledger audit confirms "
                "62% of green bond proceeds were misclassified as planting activity. "
                "Carbon sequestration claims are overstated by an estimated 70%."
            ),
            agent_weights=AGENT_WEIGHTS,
        ),
    )


# ── Legacy alias kept for orchestrator compatibility ───────────────────────

AUDIT_ID = "aud_2026_98x11"
META = _KL_META


def report_parser_state() -> ReportParserState:
    return _kl_report_parser_state()


def ledger_auditor_state() -> LedgerAuditorState:
    return _kl_ledger_auditor_state()


def media_sentinel_state() -> MediaSentinelState:
    return _kl_media_sentinel_state()


def geospatial_truth_state() -> GeospatialTruthState:
    return _kl_geospatial_truth_state()


DISCREPANCIES = _KL_DISCREPANCIES
