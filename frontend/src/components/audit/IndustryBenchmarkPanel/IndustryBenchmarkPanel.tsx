import type { RefObject } from 'react';
import { AlertTriangle, Lightbulb, Loader2, Scale } from 'lucide-react';
import type { EvidenceLayerScore, PeerIntensityRow } from '../../../types/audit';
import './IndustryBenchmarkPanel.css';

const YEAR_ORDER: Record<string, number> = {
  FY2023: 0,
  FY2024: 1,
  FY2025: 2,
  FY2026: 3,
};
const INTENSITY_UNIT = 'tCO₂e / RM million revenue';

const COLORS = {
  scope12: '#5e8c6a',
  scope3: '#4a6fa5',
  total: '#c47a5a',
  grid: 'rgba(30, 42, 58, 0.1)',
  axis: 'rgba(30, 42, 58, 0.45)',
  target: '#5e8c6a',
};

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—';
  return value.toLocaleString('en-MY', { maximumFractionDigits: decimals });
}

function intensity12(row: PeerIntensityRow): number | null {
  return row.intensity_scope_12_per_rm_million ?? row.intensity_tco2e_per_rm_million;
}

function sortPeerRows(rows: PeerIntensityRow[]): PeerIntensityRow[] {
  return [...rows].sort((a, b) => {
    if (a.is_target !== b.is_target) return a.is_target ? -1 : 1;
    const nameCmp = a.company.localeCompare(b.company);
    if (nameCmp !== 0) return nameCmp;
    const ya = YEAR_ORDER[a.data_year ?? ''] ?? 99;
    const yb = YEAR_ORDER[b.data_year ?? ''] ?? 99;
    return ya - yb;
  });
}

function groupByCompany(rows: PeerIntensityRow[]): Map<string, PeerIntensityRow[]> {
  const groups = new Map<string, PeerIntensityRow[]>();
  for (const row of sortPeerRows(rows)) {
    const list = groups.get(row.company) ?? [];
    list.push(row);
    groups.set(row.company, list);
  }
  return groups;
}

function latestRowPerCompany(rows: PeerIntensityRow[]): PeerIntensityRow[] {
  const byCompany = new Map<string, PeerIntensityRow>();
  for (const row of rows) {
    if (!row.data_found) continue;
    const existing = byCompany.get(row.company);
    const rowYear = YEAR_ORDER[row.data_year ?? ''] ?? -1;
    const existingYear = existing ? YEAR_ORDER[existing.data_year ?? ''] ?? -1 : -1;
    if (!existing || rowYear >= existingYear) {
      byCompany.set(row.company, row);
    }
  }
  return sortPeerRows([...byCompany.values()]);
}

function targetRows(rows: PeerIntensityRow[]): PeerIntensityRow[] {
  return sortPeerRows(rows.filter((r) => r.is_target && r.data_found));
}

interface ChartProps {
  rows: PeerIntensityRow[];
}

function PeerGroupedBarChart({ rows }: ChartProps) {
  const latest = latestRowPerCompany(rows);
  if (latest.length === 0) return null;

  const width = 920;
  const height = 340;
  const pad = { top: 28, right: 24, bottom: 72, left: 64 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;

  const values = latest.flatMap((r) => [
    intensity12(r),
    r.intensity_scope_3_per_rm_million,
    r.intensity_total_per_rm_million,
  ]).filter((v): v is number => v != null);

  const maxVal = Math.max(...values, 1) * 1.12;
  const groupW = chartW / latest.length;
  const barW = Math.min(18, groupW / 5);

  const yScale = (v: number) => pad.top + chartH - (v / maxVal) * chartH;

  const ticks = 5;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => (maxVal / ticks) * i);

  return (
    <figure className="ib-chart">
      <figcaption className="ib-chart__title">
        Peer intensity comparison (latest year per company)
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} className="ib-chart__svg" role="img">
        {yTicks.map((tick) => {
          const y = yScale(tick);
          return (
            <g key={tick}>
              <line x1={pad.left} y1={y} x2={width - pad.right} y2={y} stroke={COLORS.grid} />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" className="ib-chart__axis">
                {fmt(tick, 1)}
              </text>
            </g>
          );
        })}
        {latest.map((row, gi) => {
          const cx = pad.left + groupW * gi + groupW / 2;
          const metrics = [
            { key: 's12', value: intensity12(row), color: COLORS.scope12, offset: -barW - 2 },
            { key: 's3', value: row.intensity_scope_3_per_rm_million, color: COLORS.scope3, offset: 0 },
            { key: 'tot', value: row.intensity_total_per_rm_million, color: COLORS.total, offset: barW + 2 },
          ];
          const label = row.company.length > 14 ? `${row.company.slice(0, 12)}…` : row.company;
          return (
            <g key={row.company}>
              {metrics.map((m) => {
                if (m.value == null) return null;
                const barH = chartH - (yScale(m.value) - pad.top);
                const x = cx + m.offset - barW / 2;
                const y = yScale(m.value);
                return (
                  <rect
                    key={m.key}
                    x={x}
                    y={y}
                    width={barW}
                    height={barH}
                    rx={3}
                    fill={m.color}
                    opacity={row.is_target ? 1 : 0.82}
                    stroke={row.is_target ? COLORS.target : 'none'}
                    strokeWidth={row.is_target ? 1.5 : 0}
                  />
                );
              })}
              <text
                x={cx}
                y={height - pad.bottom + 18}
                textAnchor="end"
                className="ib-chart__label"
                transform={`rotate(-32, ${cx}, ${height - pad.bottom + 18})`}
              >
                {label}
              </text>
            </g>
          );
        })}
        <text
          x={16}
          y={pad.top + chartH / 2}
          transform={`rotate(-90, 16, ${pad.top + chartH / 2})`}
          className="ib-chart__ylabel"
        >
          {INTENSITY_UNIT}
        </text>
      </svg>
      <div className="ib-chart__legend">
        <span><i style={{ background: COLORS.scope12 }} /> Scope 1+2</span>
        <span><i style={{ background: COLORS.scope3 }} /> Scope 3</span>
        <span><i style={{ background: COLORS.total }} /> Total (1+2+3)</span>
      </div>
    </figure>
  );
}

function TargetTrendChart({ rows }: ChartProps) {
  const target = targetRows(rows);
  if (target.length < 2) return null;

  const width = 920;
  const height = 300;
  const pad = { top: 28, right: 24, bottom: 48, left: 64 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;

  const series = [
    { key: 's12', label: 'Scope 1+2', color: COLORS.scope12, get: intensity12 },
    { key: 's3', label: 'Scope 3', color: COLORS.scope3, get: (r: PeerIntensityRow) => r.intensity_scope_3_per_rm_million },
    { key: 'tot', label: 'Total', color: COLORS.total, get: (r: PeerIntensityRow) => r.intensity_total_per_rm_million },
  ] as const;

  const values = target.flatMap((r) =>
    series.map((s) => s.get(r)).filter((v): v is number => v != null),
  );
  const maxVal = Math.max(...values, 1) * 1.15;
  const xStep = chartW / Math.max(target.length - 1, 1);

  const yScale = (v: number) => pad.top + chartH - (v / maxVal) * chartH;
  const xScale = (i: number) => pad.left + i * xStep;

  return (
    <figure className="ib-chart">
      <figcaption className="ib-chart__title">
        Target company intensity trend (FY2023 – FY2025)
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} className="ib-chart__svg" role="img">
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = pad.top + chartH * (1 - frac);
          return (
            <g key={frac}>
              <line x1={pad.left} y1={y} x2={width - pad.right} y2={y} stroke={COLORS.grid} />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" className="ib-chart__axis">
                {fmt(maxVal * frac, 1)}
              </text>
            </g>
          );
        })}
        {series.map((s) => {
          const points = target
            .map((row, i) => {
              const v = s.get(row);
              if (v == null) return null;
              return `${xScale(i)},${yScale(v)}`;
            })
            .filter(Boolean)
            .join(' ');
          if (!points) return null;
          return (
            <g key={s.key}>
              <polyline points={points} fill="none" stroke={s.color} strokeWidth={2.5} />
              {target.map((row, i) => {
                const v = s.get(row);
                if (v == null) return null;
                return (
                  <circle
                    key={`${s.key}-${row.data_year}`}
                    cx={xScale(i)}
                    cy={yScale(v)}
                    r={4}
                    fill="#fff"
                    stroke={s.color}
                    strokeWidth={2}
                  />
                );
              })}
            </g>
          );
        })}
        {target.map((row, i) => (
          <text
            key={row.data_year}
            x={xScale(i)}
            y={height - 14}
            textAnchor="middle"
            className="ib-chart__label"
          >
            {row.data_year ?? '—'}
          </text>
        ))}
      </svg>
      <div className="ib-chart__legend">
        {series.map((s) => (
          <span key={s.key}><i style={{ background: s.color }} /> {s.label}</span>
        ))}
      </div>
    </figure>
  );
}

function Scope12RankingChart({ rows }: ChartProps) {
  const latest = latestRowPerCompany(rows)
    .filter((r) => intensity12(r) != null)
    .sort((a, b) => (intensity12(a) ?? 0) - (intensity12(b) ?? 0));

  if (latest.length === 0) return null;

  const width = 920;
  const rowH = 36;
  const pad = { top: 28, right: 24, bottom: 24, left: 200 };
  const height = pad.top + latest.length * rowH + pad.bottom;
  const chartW = width - pad.left - pad.right;
  const maxVal = Math.max(...latest.map((r) => intensity12(r) ?? 0), 1) * 1.08;

  return (
    <figure className="ib-chart">
      <figcaption className="ib-chart__title">
        Scope 1+2 intensity ranking (latest year)
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} className="ib-chart__svg" role="img">
        {latest.map((row, i) => {
          const val = intensity12(row) ?? 0;
          const y = pad.top + i * rowH + 8;
          const barW = (val / maxVal) * chartW;
          return (
            <g key={row.company}>
              <text x={pad.left - 10} y={y + 14} textAnchor="end" className="ib-chart__rank-label">
                {row.is_target ? `${row.company} ★` : row.company}
              </text>
              <rect
                x={pad.left}
                y={y}
                width={barW}
                height={20}
                rx={4}
                fill={row.is_target ? COLORS.scope12 : 'rgba(74, 111, 165, 0.75)'}
              />
              <text x={pad.left + barW + 8} y={y + 14} className="ib-chart__value">
                {fmt(val, 2)}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

interface Props {
  layer?: EvidenceLayerScore;
  busy?: boolean;
  panelRef?: RefObject<HTMLElement>;
}

export function IndustryBenchmarkPanel({ layer, busy, panelRef }: Props) {
  if (busy && !layer) {
    return (
      <section ref={panelRef} className="ib-panel ib-panel--loading gg-card" id="industry-benchmark">
        <div className="ib-panel__loading">
          <Loader2 size={22} className="ib-panel__spinner" />
          <div>
            <strong>Running industry benchmark...</strong>
            <p>Searching sustainability reports for Scope 1+2, Scope 3, and total GHG intensity across Malaysian construction peers. This may take 15-30 seconds.</p>
          </div>
        </div>
      </section>
    );
  }

  if (!layer) return null;

  const unit = layer.benchmark_unit ?? INTENSITY_UNIT;
  const rows = layer.peer_table ?? [];
  const grouped = groupByCompany(rows);
  const hasTable = rows.length > 0;
  const hasCharts = rows.some((r) => r.data_found);

  return (
    <section ref={panelRef} className="ib-panel gg-card" id="industry-benchmark">
      <header className="ib-panel__head">
        <div>
          <span className="ib-panel__eyebrow">Industry benchmark · GHG intensity</span>
          <h2 className="ib-panel__title">{layer.label}</h2>
          <p className="ib-panel__unit">
            Standard unit: <strong>{unit}</strong>
            {layer.peer_intensity_range && (
              <> · Peer range: <strong>{layer.peer_intensity_range}</strong></>
            )}
          </p>
        </div>
        <div className="ib-panel__score">
          <strong>{pct(layer.score)}</strong>
          <span>layer score · adds {pct(layer.weighted_score)}</span>
        </div>
      </header>

      {layer.benchmark_tldr && (
        <div className="ib-panel__tldr">
          <Scale size={15} />
          <div>
            <span className="ib-panel__tldr-label">TLDR</span>
            <p>{layer.benchmark_tldr}</p>
          </div>
        </div>
      )}

      {layer.benchmark_conclusion && (
        <div className={`ib-panel__verdict${layer.contradiction ? ' ib-panel__verdict--alert' : ''}`}>
          <strong>Conclusion</strong>
          <p>{layer.benchmark_conclusion}</p>
        </div>
      )}

      {!hasTable && (
        <div className="ib-panel__empty">
          <AlertTriangle size={16} />
          <div>
            <strong>No peer intensity table returned</strong>
            <p>
              {layer.rationale ||
                'The live benchmark did not return structured peer rows. Try a GHG / emissions claim, or replay verification.'}
            </p>
          </div>
        </div>
      )}

      {hasTable && (
        <div className="ib-panel__table-wrap">
          <div className="ib-panel__table-caption">
            Sustainability report comparison · Scope 1+2, Scope 3 &amp; Total · FY2023 – FY2025
          </div>
          <div className="ib-panel__table-scroll">
            <table className="ib-panel__table">
              <thead>
                <tr className="ib-panel__table-group-row">
                  <th rowSpan={2}>Company</th>
                  <th rowSpan={2}>Year</th>
                  <th rowSpan={2}>Revenue<br />(RM M)</th>
                  <th colSpan={2} className="ib-panel__th-group ib-panel__th-group--s12">Scope 1+2</th>
                  <th colSpan={2} className="ib-panel__th-group ib-panel__th-group--s3">Scope 3</th>
                  <th colSpan={2} className="ib-panel__th-group ib-panel__th-group--total">Total (1+2+3)</th>
                  <th rowSpan={2}>Source</th>
                </tr>
                <tr>
                  <th className="ib-panel__th-sub">tCO₂e</th>
                  <th className="ib-panel__th-sub">Intensity</th>
                  <th className="ib-panel__th-sub">tCO₂e</th>
                  <th className="ib-panel__th-sub">Intensity</th>
                  <th className="ib-panel__th-sub">tCO₂e</th>
                  <th className="ib-panel__th-sub">Intensity</th>
                </tr>
              </thead>
              <tbody>
                {Array.from(grouped.entries()).map(([company, companyRows]) =>
                  companyRows.map((row, idx) => (
                    <tr
                      key={`${company}-${row.data_year ?? idx}`}
                      className={row.is_target ? 'ib-panel__row--target' : undefined}
                    >
                      {idx === 0 && (
                        <td rowSpan={companyRows.length} className="ib-panel__company-cell">
                          {row.is_target && <span className="ib-badge">Target</span>}
                          <span className="ib-panel__company-name">{company}</span>
                        </td>
                      )}
                      <td className="ib-panel__year">{row.data_year ?? '—'}</td>
                      <td>{row.data_found ? fmt(row.revenue_rm_million) : '—'}</td>
                      <td>
                        {row.data_found && row.scope_1_2_tco2e != null
                          ? fmt(row.scope_1_2_tco2e, 0)
                          : <span className="ib-na">Not disclosed</span>}
                      </td>
                      <td className="ib-panel__intensity ib-panel__intensity--s12">
                        {row.data_found && intensity12(row) != null ? (
                          <strong>{fmt(intensity12(row), 2)}</strong>
                        ) : (
                          <span className="ib-na">—</span>
                        )}
                      </td>
                      <td>
                        {row.data_found && row.scope_3_tco2e != null
                          ? fmt(row.scope_3_tco2e, 0)
                          : <span className="ib-na">Not disclosed</span>}
                      </td>
                      <td className="ib-panel__intensity ib-panel__intensity--s3">
                        {row.data_found && row.intensity_scope_3_per_rm_million != null ? (
                          <strong>{fmt(row.intensity_scope_3_per_rm_million, 2)}</strong>
                        ) : (
                          <span className="ib-na">—</span>
                        )}
                      </td>
                      <td>
                        {row.data_found && row.total_scope_123_tco2e != null
                          ? fmt(row.total_scope_123_tco2e, 0)
                          : <span className="ib-na">Not disclosed</span>}
                      </td>
                      <td className="ib-panel__intensity ib-panel__intensity--total">
                        {row.data_found && row.intensity_total_per_rm_million != null ? (
                          <strong>{fmt(row.intensity_total_per_rm_million, 2)}</strong>
                        ) : (
                          <span className="ib-na">—</span>
                        )}
                      </td>
                      <td className="ib-panel__source">{row.source || '—'}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
          <p className="ib-panel__table-footnote">
            All intensity values in {unit}. Scope 3 and total rows show &ldquo;Not disclosed&rdquo; when absent from the sustainability report.
          </p>
        </div>
      )}

      {hasCharts && (
        <div className="ib-panel__charts">
          <PeerGroupedBarChart rows={rows} />
          <TargetTrendChart rows={rows} />
          <Scope12RankingChart rows={rows} />
        </div>
      )}

      {layer.evidence_snippets.length > 0 && (
        <div className="ib-panel__findings">
          <h4>Key findings</h4>
          <ul>
            {layer.evidence_snippets.map((snippet, idx) => (
              <li key={idx}>{snippet}</li>
            ))}
          </ul>
        </div>
      )}

      {layer.benchmark_insights && (
        <div className="ib-panel__insights">
          <Lightbulb size={14} />
          <div>
            <h4>Insights</h4>
            <p>{layer.benchmark_insights}</p>
          </div>
        </div>
      )}

      {layer.sources.length > 0 && (
        <div className="ib-panel__sources">
          <h4>Sources</h4>
          <div className="ib-panel__source-tags">
            {layer.sources.map((source) => (
              <span key={source}>{source}</span>
            ))}
          </div>
        </div>
      )}

      <details className="ib-panel__details">
        <summary>Scoring rationale</summary>
        <p>{layer.rationale}</p>
      </details>

      {layer.missing_evidence && (
        <div className="ib-panel__alert">
          <AlertTriangle size={13} />
          Missing or incomplete sustainability report data
        </div>
      )}
      {layer.contradiction && (
        <div className="ib-panel__alert ib-panel__alert--contradiction">
          <AlertTriangle size={13} />
          Contradiction evidence flagged in industry benchmark
        </div>
      )}
    </section>
  );
}
