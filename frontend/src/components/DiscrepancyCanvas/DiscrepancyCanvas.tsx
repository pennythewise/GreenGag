import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { AuditPayload, Discrepancy } from '../../types/audit';
import { useSelection } from '../../lib/selection';
import { severityColor } from '../../lib/format';
import './DiscrepancyCanvas.css';

interface Line {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
}

function evidenceFor(d: Discrepancy, audit: AuditPayload) {
  if (d.ledger_row_id) {
    const row = audit.agent_states.LedgerAuditorAgent.rows.find((r) => r.id === d.ledger_row_id);
    return {
      kind: 'Ledger' as const,
      title: row ? `${row.invoice_id} · ${row.vendor}` : 'Ledger line-item',
      detail: row ? row.material : '',
      source: 'LedgerAuditorAgent',
    };
  }
  if (d.geo_anchor) {
    const g = audit.agent_states.GeospatialTruthAgent.metrics;
    const vetoed = g.layers.filter((l) => l.veto);
    const topLayer = vetoed[0] ?? g.layers[0];
    return {
      kind: 'Satellite' as const,
      title: topLayer ? `${topLayer.source} · ${topLayer.parameter}` : 'Satellite',
      detail: topLayer
        ? `Observed variance +${Math.round(topLayer.observed_variance_pct * 100)}% · ${vetoed.length} layer(s) flagged`
        : 'Multi-layer anomaly detected',
      source: 'GeospatialTruthAgent',
    };
  }
  return {
    kind: 'Media' as const,
    title: 'Public-record contradiction',
    detail: audit.agent_states.MediaSentinelAgent.articles[0]?.headline ?? '',
    source: 'MediaSentinelAgent',
  };
}

/**
 * The Discrepancy Canvas (PRD §2.2): an interactive split viewport. Selecting a
 * high-risk discrepancy draws an animated SVG anchor line from the suspicious
 * ESG claim (left) to the contradicting evidence — ledger line-item, satellite
 * pixel cluster, or public record (right).
 */
export function DiscrepancyCanvas({ audit }: { audit: AuditPayload }) {
  const { activeClaimId, activeDiscrepancyId, setActiveClaim, setActiveDiscrepancy } =
    useSelection();
  const containerRef = useRef<HTMLDivElement>(null);
  const claimRefs = useRef<Map<string, HTMLElement>>(new Map());
  const evidenceRefs = useRef<Map<string, HTMLElement>>(new Map());
  const [line, setLine] = useState<Line | null>(null);

  const claimById = Object.fromEntries(
    audit.agent_states.ReportParserAgent.extracted_claims.map((c) => [c.id, c]),
  );

  // The discrepancy in focus: explicit selection, or derived from an active claim.
  const selected =
    audit.discrepancies.find((d) => d.id === activeDiscrepancyId) ??
    audit.discrepancies.find((d) => d.claim_id === activeClaimId) ??
    null;

  const recompute = useCallback(() => {
    if (!selected || !containerRef.current) {
      setLine(null);
      return;
    }
    const claimEl = claimRefs.current.get(selected.claim_id);
    const evidenceEl = evidenceRefs.current.get(selected.id);
    if (!claimEl || !evidenceEl) {
      setLine(null);
      return;
    }
    const base = containerRef.current.getBoundingClientRect();
    const a = claimEl.getBoundingClientRect();
    const b = evidenceEl.getBoundingClientRect();
    setLine({
      x1: a.right - base.left,
      y1: a.top + a.height / 2 - base.top,
      x2: b.left - base.left,
      y2: b.top + b.height / 2 - base.top,
      color: severityColor(selected.severity),
    });
  }, [selected]);

  useLayoutEffect(recompute, [recompute, audit]);

  useEffect(() => {
    const ro = new ResizeObserver(recompute);
    if (containerRef.current) ro.observe(containerRef.current);
    window.addEventListener('scroll', recompute, true);
    return () => {
      ro.disconnect();
      window.removeEventListener('scroll', recompute, true);
    };
  }, [recompute]);

  const handleSelect = (d: Discrepancy) => {
    const isActive = activeDiscrepancyId === d.id;
    setActiveDiscrepancy(isActive ? null : d.id);
    setActiveClaim(isActive ? null : d.claim_id);
  };

  const midX = line ? (line.x1 + line.x2) / 2 : 0;

  return (
    <div className="gg-card disc">
      <div className="gg-card__header">
        <div>
          <div className="gg-card__title">Discrepancy Canvas</div>
          <div className="gg-card__eyebrow">Data triangulation lineage · click a finding to trace</div>
        </div>
        <span className="gg-pill">{audit.discrepancies.length} linkages</span>
      </div>

      <div className="disc__viewport" ref={containerRef}>
        {/* SVG anchor-line overlay (animates in on click — never static). */}
        <svg className="disc__overlay" aria-hidden>
          {line && (
            <>
              <path
                key={`${selected?.id}`}
                className="disc__link"
                d={`M ${line.x1} ${line.y1} C ${midX} ${line.y1}, ${midX} ${line.y2}, ${line.x2} ${line.y2}`}
                stroke={line.color}
              />
              <circle className="disc__anchor" cx={line.x1} cy={line.y1} r="5" fill={line.color} />
              <circle className="disc__anchor" cx={line.x2} cy={line.y2} r="5" fill={line.color} />
            </>
          )}
        </svg>

        {/* Left: suspicious ESG claims. */}
        <div className="disc__col disc__col--claims">
          <div className="disc__col-head">ESG Report Claim</div>
          {audit.discrepancies.map((d) => {
            const claim = claimById[d.claim_id];
            const active = selected?.id === d.id;
            return (
              <div
                key={d.id}
                ref={(el) => {
                  if (el) claimRefs.current.set(d.claim_id, el);
                }}
                className={`disc__node disc__node--claim ${active ? 'is-active' : ''}`}
              >
                <span className="disc__node-tag">{claim?.label ?? d.claim_id}</span>
                <span className="disc__node-text">“{claim?.raw_text ?? ''}”</span>
              </div>
            );
          })}
        </div>

        {/* Center: the discrepancy selectors. */}
        <div className="disc__col disc__col--findings">
          <div className="disc__col-head">Finding</div>
          {audit.discrepancies.map((d) => {
            const active = selected?.id === d.id;
            return (
              <button
                key={d.id}
                className={`disc__finding ${active ? 'is-active' : ''}`}
                style={{ ['--sev' as string]: severityColor(d.severity) }}
                onClick={() => handleSelect(d)}
              >
                <span className="disc__sev" style={{ background: severityColor(d.severity) }} />
                <span className="disc__finding-text">{d.summary}</span>
              </button>
            );
          })}
        </div>

        {/* Right: contradicting evidence. */}
        <div className="disc__col disc__col--evidence">
          <div className="disc__col-head">Contradicting Evidence</div>
          {audit.discrepancies.map((d) => {
            const ev = evidenceFor(d, audit);
            const active = selected?.id === d.id;
            return (
              <div
                key={d.id}
                ref={(el) => {
                  if (el) evidenceRefs.current.set(d.id, el);
                }}
                className={`disc__node disc__node--evidence ${active ? 'is-active' : ''}`}
              >
                <span className={`disc__ev-kind disc__ev-kind--${ev.kind.toLowerCase()}`}>{ev.kind}</span>
                <span className="disc__node-title">{ev.title}</span>
                <span className="disc__node-detail">{ev.detail}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
