import { Fragment, useState, type RefObject } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, Clock, Lightbulb, Loader2, Scale, Users } from 'lucide-react';
import type { EvidenceLayerScore, JobstreetReviewRow, PeerIntensityRow } from '../../../types/audit';
import './IndustryBenchmarkPanel.css';

const YEAR_ORDER: Record<string, number> = {
  FY2023: 0, FY2024: 1, FY2025: 2, FY2026: 3,
};
const INTENSITY_UNIT = 'tCO₂e / RM million revenue';

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—';
  return value.toLocaleString('en-MY', { maximumFractionDigits: decimals });
}

function sortPeerRows(rows: PeerIntensityRow[]): PeerIntensityRow[] {
  return [...rows].sort((a, b) => {
    if (a.is_target !== b.is_target) return a.is_target ? -1 : 1;
    const nameCmp = a.company.localeCompare(b.company);
    if (nameCmp !== 0) return nameCmp;
    return (YEAR_ORDER[a.data_year ?? ''] ?? 99) - (YEAR_ORDER[b.data_year ?? ''] ?? 99);
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
    if (!existing || rowYear >= existingYear) byCompany.set(row.company, row);
  }
  return sortPeerRows([...byCompany.values()]);
}

function scope12Label(row: PeerIntensityRow): string {
  if (row.scope_3_included || row.emissions_note) {
    return `Scope 1+2 ${row.emissions_note || '(Scope 3 included)'}`;
  }
  return 'Scope 1+2';
}

function IntensityBarChart({ rows }: { rows: PeerIntensityRow[] }) {
  const latest = latestRowPerCompany(rows).filter(
    (r) => r.intensity_tco2e_per_rm_million != null,
  );
  if (latest.length === 0) return null;

  const maxVal = Math.max(...latest.map((r) => r.intensity_tco2e_per_rm_million ?? 0), 1) * 1.1;
  const width = 900;
  const rowH = 32;
  const pad = { top: 24, left: 180, right: 80, bottom: 16 };
  const height = pad.top + latest.length * rowH + pad.bottom;

  return (
    <figure className="ib-chart">
      <figcaption className="ib-chart__title">Scope 1+2 intensity ranking (latest year)</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} className="ib-chart__svg" role="img">
        {latest.map((row, i) => {
          const val = row.intensity_tco2e_per_rm_million ?? 0;
          const y = pad.top + i * rowH;
          const barW = (val / maxVal) * (width - pad.left - pad.right);
          return (
            <g key={row.company}>
              <text x={pad.left - 8} y={y + 18} textAnchor="end" className="ib-chart__rank-label">
                {row.is_target ? `${row.company} ★` : row.company}
              </text>
              <rect
                x={pad.left}
                y={y + 4}
                width={barW}
                height={18}
                rx={4}
                fill={row.is_target ? '#5e8c6a' : 'rgba(74, 111, 165, 0.8)'}
              />
              <text x={pad.left + barW + 8} y={y + 18} className="ib-chart__value">
                {fmt(val, 2)} · {row.data_year ?? '—'}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

function truncate(text: string, max = 120): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max).trim()}…`;
}

function formatReviewDate(date: string): string {
  if (!date) return '—';
  const [year, month] = date.split('-');
  if (!year) return date;
  if (!month) return year;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const idx = parseInt(month, 10) - 1;
  return idx >= 0 && idx < 12 ? `${months[idx]} ${year}` : date;
}

function JobstreetReviewExpand({
  row,
  onClose,
}: {
  row: JobstreetReviewRow;
  onClose: () => void;
}) {
  const reviews = [...(row.sample_reviews ?? [])].sort(
    (a, b) => (b.review_date || '').localeCompare(a.review_date || ''),
  );

  return (
    <div className="ib-js-expand">
      <div className="ib-js-expand__head">
        <div>
          <strong>{row.company}</strong>
          <span className="ib-js-expand__sub">Review timeline & trend analysis</span>
        </div>
        <button type="button" className="ib-js-expand__close" onClick={onClose}>
          Hide
        </button>
      </div>

      {row.timeline_note && (
        <div className="ib-js-expand__timeline">
          <Clock size={14} />
          <p>{row.timeline_note}</p>
        </div>
      )}

      {row.trend_summary && (
        <div className="ib-js-expand__trend">
          <Lightbulb size={14} />
          <div>
            <span className="ib-js-expand__label">Trend summary</span>
            <p>{row.trend_summary}</p>
          </div>
        </div>
      )}

      {reviews.length > 0 ? (
        <div className="ib-js-expand__reviews">
          <span className="ib-js-expand__label">Sample reviews (newest first)</span>
          <ul>
            {reviews.map((review, idx) => (
              <li key={`${review.review_date}-${idx}`} className="ib-js-review">
                <div className="ib-js-review__meta">
                  <span className="ib-js-review__date">{formatReviewDate(review.review_date)}</span>
                  <span className="ib-js-review__role">{review.role || 'Employee'}</span>
                  {review.rating != null && (
                    <span className="ib-js-review__rating">{review.rating.toFixed(1)}/5</span>
                  )}
                  {review.tenure && <span className="ib-js-review__tenure">{review.tenure}</span>}
                </div>
                {review.positive && (
                  <p><strong>Positive:</strong> {review.positive}</p>
                )}
                {review.negative && (
                  <p><strong>Challenges:</strong> {review.negative}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="ib-js-expand__empty">No dated review excerpts available — run live benchmark to scrape Jobstreet.</p>
      )}

      {row.jobstreet_url && (
        <a href={row.jobstreet_url} target="_blank" rel="noreferrer" className="ib-link ib-js-expand__link">
          View all reviews on Jobstreet →
        </a>
      )}
    </div>
  );
}

function JobstreetRatingChart({ rows }: { rows: JobstreetReviewRow[] }) {
  const sorted = [...rows].sort((a, b) => (b.overall_rating ?? 0) - (a.overall_rating ?? 0));
  if (sorted.length === 0) return null;

  return (
    <figure className="ib-chart">
      <figcaption className="ib-chart__title">Jobstreet overall rating comparison</figcaption>
      <div className="ib-js-bars">
        {sorted.map((row) => {
          const rating = row.overall_rating ?? 0;
          const pctWidth = (rating / 5) * 100;
          return (
            <div key={row.company} className={`ib-js-bar${row.is_target ? ' ib-js-bar--target' : ''}`}>
              <span className="ib-js-bar__label">
                {row.is_target && <span className="ib-badge">Target</span>}
                {row.company}
              </span>
              <div className="ib-js-bar__track">
                <span style={{ width: `${pctWidth}%` }} />
              </div>
              <span className="ib-js-bar__value">{rating ? rating.toFixed(1) : '—'}/5</span>
            </div>
          );
        })}
      </div>
    </figure>
  );
}

interface Props {
  layer?: EvidenceLayerScore;
  busy?: boolean;
  panelRef?: RefObject<HTMLElement>;
}

export function IndustryBenchmarkPanel({ layer, busy, panelRef }: Props) {
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);

  const toggleCompany = (company: string) => {
    setExpandedCompany((prev) => (prev === company ? null : company));
  };

  if (busy && !layer) {
    return (
      <section ref={panelRef} className="ib-panel ib-panel--loading gg-card" id="industry-benchmark">
        <div className="ib-panel__loading">
          <Loader2 size={22} className="ib-panel__spinner" />
          <div>
            <strong>Running industry benchmark…</strong>
            <p>Searching sustainability reports or Jobstreet employee reviews. This may take 15–30 seconds.</p>
          </div>
        </div>
      </section>
    );
  }

  if (!layer) return null;

  const unit = layer.benchmark_unit ?? INTENSITY_UNIT;
  const rows = layer.peer_table ?? [];
  const jsRows = layer.jobstreet_table ?? [];
  const grouped = groupByCompany(rows);
  const hasGhgTable = rows.length > 0;
  const hasJobstreet = jsRows.length > 0;
  const isSocial = hasJobstreet && !hasGhgTable;

  return (
    <section ref={panelRef} className="ib-panel gg-card" id="industry-benchmark">
      <header className="ib-panel__head">
        <div>
          <span className="ib-panel__eyebrow">
            {isSocial ? 'Industry benchmark · Jobstreet reviews' : 'Industry benchmark · GHG intensity'}
          </span>
          <h2 className="ib-panel__title">{layer.label}</h2>
          <p className="ib-panel__unit">
            {isSocial ? (
              <>Source: <strong>Jobstreet employee reviews</strong></>
            ) : (
              <>Unit: <strong>{unit}</strong>
                {layer.peer_intensity_range && <> · Peer range: <strong>{layer.peer_intensity_range}</strong></>}
              </>
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

      {hasGhgTable && (
        <>
          <div className="ib-panel__table-wrap">
            <div className="ib-panel__table-caption">
              Scope 1+2 GHG intensity · tCO₂e / RM million revenue
            </div>
            <div className="ib-panel__table-scroll">
              <table className="ib-panel__table ib-panel__table--ghg">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Year</th>
                    <th>Revenue (RM M)</th>
                    <th>Scope 1+2 (tCO₂e)</th>
                    <th>Intensity</th>
                    <th>Note</th>
                    <th>Source</th>
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
                        <td className="ib-panel__intensity">
                          {row.data_found && row.intensity_tco2e_per_rm_million != null ? (
                            <strong>{fmt(row.intensity_tco2e_per_rm_million, 2)}</strong>
                          ) : (
                            <span className="ib-na">—</span>
                          )}
                        </td>
                        <td className="ib-panel__note">
                          {row.scope_3_included || row.emissions_note ? (
                            <span className="ib-note-tag">{scope12Label(row)}</span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="ib-panel__source">{row.source || '—'}</td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <IntensityBarChart rows={rows} />
        </>
      )}

      {hasJobstreet && (
        <>
          <div className="ib-panel__timeline-note">
            <Clock size={14} />
            <p>
              Employee reviews are dated — older posts (e.g. 2020–2023) may not reflect culture changes
              claimed in 2025+ sustainability reports. Click a company name to expand sample reviews and trend analysis.
            </p>
          </div>
          <div className="ib-panel__table-wrap">
            <div className="ib-panel__table-caption">
              <Users size={14} /> Jobstreet employee review comparison
            </div>
            <div className="ib-panel__table-scroll">
              <table className="ib-panel__table ib-panel__table--js">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Overall</th>
                    <th>Reviews</th>
                    <th>Work/life</th>
                    <th>Career</th>
                    <th>Environment</th>
                    <th>Recommend</th>
                    <th>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {jsRows.map((row) => {
                    const isExpanded = expandedCompany === row.company;
                    return (
                      <Fragment key={row.company}>
                        <tr
                          className={[
                            row.is_target ? 'ib-panel__row--target' : undefined,
                            isExpanded ? 'ib-panel__row--expanded' : undefined,
                          ].filter(Boolean).join(' ') || undefined}
                        >
                          <td className="ib-panel__company-cell">
                            {row.is_target && <span className="ib-badge">Target</span>}
                            <button
                              type="button"
                              className={`ib-js-company-toggle${isExpanded ? ' ib-js-company-toggle--open' : ''}`}
                              onClick={() => toggleCompany(row.company)}
                              aria-expanded={isExpanded}
                            >
                              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                              <span>{row.company}</span>
                            </button>
                          </td>
                          <td><strong>{row.overall_rating != null ? row.overall_rating.toFixed(1) : '—'}</strong></td>
                          <td>{row.review_count ?? '—'}</td>
                          <td>{row.work_life_balance != null ? row.work_life_balance.toFixed(1) : '—'}</td>
                          <td>{row.career_development != null ? row.career_development.toFixed(1) : '—'}</td>
                          <td>{row.working_environment != null ? row.working_environment.toFixed(1) : '—'}</td>
                          <td>{row.recommend_pct != null ? `${row.recommend_pct}%` : '—'}</td>
                          <td className="ib-panel__summary-cell">
                            {row.ai_summary ? truncate(row.ai_summary) : '—'}
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="ib-panel__row--detail">
                            <td colSpan={8}>
                              <JobstreetReviewExpand row={row} onClose={() => setExpandedCompany(null)} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <JobstreetRatingChart rows={jsRows} />
        </>
      )}

      {!hasGhgTable && !hasJobstreet && (
        <div className="ib-panel__empty">
          <AlertTriangle size={16} />
          <div>
            <strong>No benchmark table returned</strong>
            <p>{layer.rationale || 'Replay verification on a GHG or social claim.'}</p>
          </div>
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
    </section>
  );
}
