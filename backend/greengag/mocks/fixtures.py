"""Deterministic fixtures for GREENGAG_DATA_MODE=mock.

Mirrors frontend/src/mocks/auditPayload.ts. Each mock agent returns its slice
from here; the orchestrator assembles them into the AuditPayload.
"""

from __future__ import annotations

import math

from greengag.models.schemas import (
    AuditMeta,
    Discrepancy,
    ExtractedClaim,
    GeoMetrics,
    GeoPolygon,
    GeospatialTruthState,
    HeatPixel,
    HighlightBox,
    LedgerAuditorState,
    LedgerMetrics,
    LedgerRow,
    MediaArticle,
    MediaSentinelState,
    PdfBlock,
    PdfDocument,
    PdfPage,
    ReportParserState,
    TimeSeriesPoint,
)

AUDIT_ID = "aud_2026_98x11"

META = AuditMeta(
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

# Per-agent weights for the Weighted Integrity Index (geospatial = 50%).
AGENT_WEIGHTS: dict[str, float] = {
    "GeospatialTruthAgent": 0.50,
    "LedgerAuditorAgent": 0.25,
    "MediaSentinelAgent": 0.15,
    "ReportParserAgent": 0.10,
}


def _time_series() -> list[TimeSeriesPoint]:
    raw = [
        ("2025-06", 100, 100), ("2025-07", 96, 101), ("2025-08", 92, 99),
        ("2025-09", 87, 102), ("2025-10", 83, 100), ("2025-11", 79, 103),
        ("2025-12", 75, 101), ("2026-01", 72, 104), ("2026-02", 70, 100),
        ("2026-03", 70, 102), ("2026-04", 70, 105), ("2026-05", 70, 103),
    ]
    return [TimeSeriesPoint(date=d, claimed=c, observed=o) for d, c, o in raw]


def _heatmap() -> list[HeatPixel]:
    pixels: list[HeatPixel] = []
    min_lng, min_lat, step = 101.686, 3.139, 0.0008
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


def report_parser_state() -> ReportParserState:
    return ReportParserState(
        status="SUCCESS",
        risk_contribution=0.10,
        progress=1.0,
        active_tool="pdf_extractor::gpt-4o",
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


def ledger_auditor_state() -> LedgerAuditorState:
    return LedgerAuditorState(
        status="ALERT",
        risk_contribution=0.85,
        progress=1.0,
        active_tool="ledger_query::postgres(internal)",
        rationale_trail=[
            "Connected to internal procurement ledger (read-only).",
            "Pulled 142 purchase orders tagged to project KL-CENTRAL-EXP.",
            "Cross-referenced vendor index against approved green-material provider lists.",
            "Verified green spend totals USD 180,000 - only 15% of the claimed 1.2M budget.",
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
                      note="PO swapped from Vertua to standard OPC - contradicts material claim."),
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


def media_sentinel_state() -> MediaSentinelState:
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


def geospatial_truth_state() -> GeospatialTruthState:
    return GeospatialTruthState(
        status="ALERT",
        risk_contribution=0.95,
        progress=1.0,
        active_tool="sentinel5p::tropomi-no2",
        rationale_trail=[
            "Pulled time-series raster array values over the polygon target (12 months).",
            "Calculated running mean of tropospheric NO2 vertical column density.",
            "Compared observed trend against the claimed 30% reduction curve.",
            "Observed variance vs. claim: +40% (emissions did not fall).",
            "Flatlined output indicates zero emissions reduction observed.",
            "VETO ASSERTED: physical evidence contradicts the corporate commitment.",
        ],
        metrics=GeoMetrics(
            satellite_source="Sentinel-5P_TROPOMI",
            observed_gas_variance_percentage=0.40,
            confidence_index=0.92,
            veto=True,
        ),
        unit="NO2 tropospheric column (normalized index)",
        time_series=_time_series(),
        heatmap=_heatmap(),
    )


DISCREPANCIES = [
    Discrepancy(id="d1", severity="critical",
                summary="Report claims exclusive Vertua low-carbon concrete, but invoice #INV-9981 shows a USD 540K standard OPC purchase.",
                claim_id="c-material", ledger_row_id="l3"),
    Discrepancy(id="d2", severity="high",
                summary='USD 1.2M "green budget" claim contradicted by USD 480K routed to non-certified suppliers.',
                claim_id="c-spend", ledger_row_id="l4"),
    Discrepancy(id="d3", severity="critical",
                summary="Claimed 30% emissions reduction; Sentinel-5P shows a +40% variance flatline over the target polygon.",
                claim_id="c-reduction", geo_anchor={"lng": 101.6884, "lat": 3.1414}),
    Discrepancy(id="d4", severity="high",
                summary='"Zero environmental incidents" contradicted by an NGO-logged November slurry discharge.',
                claim_id="c-incidents"),
]
