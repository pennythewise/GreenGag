import type { AuditPayload, TimeSeriesPoint, HeatPixel } from '../types/audit';

/* ── Geospatial fixtures ──────────────────────────────────────────────── */

// 12-month series: company claims a steady reduction; satellite observes a flatline.
const TIME_SERIES: TimeSeriesPoint[] = [
  { date: '2025-06', claimed: 100, observed: 100 },
  { date: '2025-07', claimed: 96, observed: 101 },
  { date: '2025-08', claimed: 92, observed: 99 },
  { date: '2025-09', claimed: 87, observed: 102 },
  { date: '2025-10', claimed: 83, observed: 100 },
  { date: '2025-11', claimed: 79, observed: 103 },
  { date: '2025-12', claimed: 75, observed: 101 },
  { date: '2026-01', claimed: 72, observed: 104 },
  { date: '2026-02', claimed: 70, observed: 100 },
  { date: '2026-03', claimed: 70, observed: 102 },
  { date: '2026-04', claimed: 70, observed: 105 },
  { date: '2026-05', claimed: 70, observed: 103 },
];

// Heat grid over the KL Central polygon — hot core where the factory sits.
const HEATMAP: HeatPixel[] = (() => {
  const pixels: HeatPixel[] = [];
  const minLng = 101.686;
  const minLat = 3.139;
  const step = 0.0008;
  for (let i = 0; i < 5; i++) {
    for (let j = 0; j < 5; j++) {
      const dx = i - 2;
      const dy = j - 2;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const intensity = Math.max(0, 1 - dist / 3) ** 1.5;
      pixels.push({
        lng: minLng + i * step,
        lat: minLat + j * step,
        intensity: Number(intensity.toFixed(2)),
      });
    }
  }
  return pixels;
})();

/* ── The canonical sample audit ───────────────────────────────────────── */

export const MOCK_AUDIT: AuditPayload = {
  audit_id: 'aud_2026_98x11',
  meta: {
    target_entity: 'Malaya BuildCorp Group',
    project_name: 'KL Central Eco-Tower Expansion',
    coordinates: {
      type: 'Polygon',
      coordinates: [
        [
          [101.686, 3.139],
          [101.69, 3.139],
          [101.69, 3.143],
          [101.686, 3.143],
          [101.686, 3.139],
        ],
      ],
    },
  },

  agent_states: {
    ReportParserAgent: {
      status: 'SUCCESS',
      risk_contribution: 0.1,
      progress: 1,
      active_tool: 'pdf_extractor::claude-opus-4-8',
      rationale_trail: [
        'Loaded ESG report "2025 Sustainability & Net-Zero Pathway" (48 pages).',
        'Stripped promotional cover, foreword, and 11 stock-photo pages.',
        'Parsed PDF structure lines 112–140 for measurable commitments.',
        'Identified explicit emission-reduction commitment clause (30% by 2026).',
        'Extracted material classification + self-reported green budget.',
        'Normalized 3 claims into structured JSON for downstream agents.',
      ],
      document: {
        title: '2025 Sustainability & Net-Zero Pathway',
        pages: [
          {
            page: 4,
            heading: 'Our Decarbonization Commitment',
            blocks: [
              {
                id: 'b1',
                text: 'Malaya BuildCorp is proud to lead the region toward a regenerative built environment.',
              },
              {
                id: 'b2',
                text: 'We commit to a 30% reduction in operational carbon intensity across the KL Central Eco-Tower Expansion by year-end 2026.',
                claim_id: 'c-reduction',
              },
              {
                id: 'b3',
                text: 'Every structural pour on this flagship project uses Cemex Vertua low-carbon concrete, sourced exclusively from certified green suppliers.',
                claim_id: 'c-material',
              },
            ],
          },
          {
            page: 12,
            heading: 'Green Capital Allocation',
            blocks: [
              {
                id: 'b4',
                text: 'A dedicated sustainability budget of USD 1.2 million has been ring-fenced for verified low-carbon materials procurement on this project.',
                claim_id: 'c-spend',
              },
              {
                id: 'b5',
                text: 'We recorded zero environmental incidents at the construction site during the reporting period.',
                claim_id: 'c-incidents',
              },
            ],
          },
        ],
      },
      extracted_claims: [
        {
          id: 'c-reduction',
          label: 'Carbon reduction commitment',
          raw_text: '30% reduction in operational carbon intensity by year-end 2026',
          claimed_reduction_pct: 30,
          highlight: { page: 4, x: 8, y: 41, w: 84, h: 9 },
        },
        {
          id: 'c-material',
          label: 'Material classification',
          raw_text: 'Cemex Vertua low-carbon concrete, certified green suppliers',
          material_class: 'Cemex Vertua Low-Carbon Concrete',
          highlight: { page: 4, x: 8, y: 55, w: 84, h: 9 },
        },
        {
          id: 'c-spend',
          label: 'Self-reported green spend',
          raw_text: 'USD 1.2 million ring-fenced for verified low-carbon materials',
          stated_spend_usd: 1_200_000,
          highlight: { page: 12, x: 8, y: 30, w: 84, h: 8 },
        },
        {
          id: 'c-incidents',
          label: 'Zero-incident claim',
          raw_text: 'zero environmental incidents at the construction site',
          highlight: { page: 12, x: 8, y: 47, w: 84, h: 8 },
        },
      ],
    },

    LedgerAuditorAgent: {
      status: 'ALERT',
      risk_contribution: 0.85,
      progress: 1,
      active_tool: 'ledger_query::postgres(internal)',
      rationale_trail: [
        'Connected to internal procurement ledger (read-only).',
        'Pulled 142 purchase orders tagged to project KL-CENTRAL-EXP.',
        'Cross-referenced vendor index against approved green-material provider lists.',
        'Verified green spend totals USD 180,000 — only 15% of the claimed 1.2M budget.',
        'Detected standard cement-grade purchase-order swap on invoice #INV-9981.',
        'Bait-and-switch pattern: 85% of spend routed to high-carbon suppliers.',
      ],
      extracted_metrics: {
        verified_green_spend_usd: 180_000,
        unverified_standard_spend_usd: 1_020_000,
        green_ratio: 0.15,
      },
      rows: [
        {
          id: 'l1',
          date: '2025-08-02',
          invoice_id: 'INV-9712',
          vendor: 'Cemex Vertua (Certified)',
          material: 'Vertua Low-Carbon Concrete',
          category: 'green',
          amount_usd: 120_000,
          flagged: false,
        },
        {
          id: 'l2',
          date: '2025-09-15',
          invoice_id: 'INV-9844',
          vendor: 'Greenform Rebar Co.',
          material: 'Recycled Structural Steel',
          category: 'green',
          amount_usd: 60_000,
          flagged: false,
        },
        {
          id: 'l3',
          date: '2025-10-28',
          invoice_id: 'INV-9981',
          vendor: 'Klang Standard Cement Sdn Bhd',
          material: 'OPC Grade 42.5 (high-carbon)',
          category: 'standard',
          amount_usd: 540_000,
          flagged: true,
          linked_claim_id: 'c-material',
          note: 'PO swapped from Vertua to standard OPC — contradicts material claim.',
        },
        {
          id: 'l4',
          date: '2025-12-11',
          invoice_id: 'INV-10233',
          vendor: 'Klang Standard Cement Sdn Bhd',
          material: 'OPC Grade 42.5 (high-carbon)',
          category: 'standard',
          amount_usd: 300_000,
          flagged: true,
          linked_claim_id: 'c-spend',
          note: 'Charged against the green budget line but non-certified material.',
        },
        {
          id: 'l5',
          date: '2026-02-03',
          invoice_id: 'INV-10588',
          vendor: 'PerakAggregate Holdings',
          material: 'Standard Aggregate Mix',
          category: 'standard',
          amount_usd: 180_000,
          flagged: true,
          linked_claim_id: 'c-spend',
          note: 'Not on approved green provider list.',
        },
      ],
    },

    MediaSentinelAgent: {
      status: 'ALERT',
      risk_contribution: 0.7,
      progress: 1,
      active_tool: 'web_scraper::nlp-classifier',
      rationale_trail: [
        'Scraped 1,204 documents across news, NGO databases, and community boards.',
        'Ran NLP contradiction classifier against extracted corporate claims.',
        'Surfaced 3 high-signal contradictions to the "zero incidents" claim.',
        'Greenpeace SEA flagged an unreported slurry discharge in Nov 2025.',
        'Local board reports match the satellite anomaly window.',
      ],
      articles: [
        {
          id: 'm1',
          headline: 'Residents report grey slurry runoff near KL Central tower site',
          source: 'Klang Valley Community Board',
          url: 'https://example.org/community/klang-slurry',
          published: '2025-11-09',
          snippet:
            'Multiple residents posted photos of grey discharge entering the storm drain adjacent to the Eco-Tower construction site over the weekend.',
          contradiction_score: 0.82,
          tag: 'community',
        },
        {
          id: 'm2',
          headline: 'Greenpeace SEA logs unreported discharge at "eco" megaproject',
          source: 'Greenpeace Southeast Asia',
          url: 'https://example.org/ngo/greenpeace-discharge',
          published: '2025-11-21',
          snippet:
            'Field monitors recorded an industrial slurry discharge that does not appear in the developer’s self-reported incident log.',
          contradiction_score: 0.91,
          tag: 'ngo',
        },
        {
          id: 'm3',
          headline: 'BuildCorp touts "zero-incident" record amid scrutiny',
          source: 'The Malayan Ledger',
          url: 'https://example.org/news/buildcorp-zero-incident',
          published: '2026-01-14',
          snippet:
            'The developer reiterated a flawless environmental record this week, even as regulators confirmed an open inquiry into a November discharge.',
          contradiction_score: 0.76,
          tag: 'news',
        },
        {
          id: 'm4',
          headline: 'Quarterly air-quality readings steady near industrial KL belt',
          source: 'Regional Environment Wire',
          url: 'https://example.org/news/air-quality-steady',
          published: '2026-03-02',
          snippet:
            'Ambient monitoring stations show no measurable improvement in NO₂ levels across the central construction corridor.',
          contradiction_score: 0.58,
          tag: 'news',
        },
      ],
    },

    GeospatialTruthAgent: {
      status: 'ALERT',
      risk_contribution: 0.95,
      progress: 1,
      active_tool: 'sentinel5p::tropomi-no2',
      rationale_trail: [
        'Pulled time-series raster array values over the polygon target (12 months).',
        'Calculated running mean of tropospheric NO₂ vertical column density.',
        'Compared observed trend against the claimed 30% reduction curve.',
        'Observed variance vs. claim: +40% (emissions did not fall).',
        'Flatlined output indicates zero emissions reduction observed.',
        'VETO ASSERTED: physical evidence contradicts the corporate commitment.',
      ],
      metrics: {
        satellite_source: 'Sentinel-5P_TROPOMI',
        observed_gas_variance_percentage: 0.4,
        confidence_index: 0.92,
        veto: true,
      },
      unit: 'NO₂ tropospheric column (normalized index)',
      time_series: TIME_SERIES,
      heatmap: HEATMAP,
    },
  },

  discrepancies: [
    {
      id: 'd1',
      severity: 'critical',
      summary:
        'Report claims exclusive Vertua low-carbon concrete, but invoice #INV-9981 shows a USD 540K standard OPC purchase.',
      claim_id: 'c-material',
      ledger_row_id: 'l3',
    },
    {
      id: 'd2',
      severity: 'high',
      summary:
        'USD 1.2M "green budget" claim contradicted by USD 480K routed to non-certified suppliers.',
      claim_id: 'c-spend',
      ledger_row_id: 'l4',
    },
    {
      id: 'd3',
      severity: 'critical',
      summary:
        'Claimed 30% emissions reduction; Sentinel-5P shows a +40% variance flatline over the target polygon.',
      claim_id: 'c-reduction',
      geo_anchor: { lng: 101.6884, lat: 3.1414 },
    },
    {
      id: 'd4',
      severity: 'high',
      summary:
        '"Zero environmental incidents" contradicted by an NGO-logged November slurry discharge.',
      claim_id: 'c-incidents',
    },
  ],

  global_metrics: {
    weighted_risk_score: 0.815,
    confidence_score: 0.89,
    final_verdict: 'CRITICAL_RISK_FRAUD_DETECTED',
    executive_summary:
      'Malaya BuildCorp’s 30% decarbonization claim for the KL Central Eco-Tower is not supported by physical, financial, or public evidence. Satellite NO₂ readings show no reduction (+40% variance, flatline), while 85% of procurement spend was routed to high-carbon suppliers despite a "green budget" claim. An NGO-logged discharge contradicts the zero-incident statement. The Geospatial Truth Agent has asserted its veto. Verdict: Critical greenwashing risk — these findings require human review and do not constitute a legal determination.',
    agent_weights: {
      GeospatialTruthAgent: 0.5,
      LedgerAuditorAgent: 0.25,
      MediaSentinelAgent: 0.15,
      ReportParserAgent: 0.1,
    },
  },
};
