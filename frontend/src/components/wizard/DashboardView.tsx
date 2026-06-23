import { Download, RefreshCw, ShieldAlert, ExternalLink } from 'lucide-react';
import type { AgentKey, AuditPayload } from '../../types/audit';
import { RiskScoreRing } from '../audit/RiskScoreRing/RiskScoreRing';
import { fmtPct } from '../../lib/format';
import './wizard.css';

interface Props {
  audit: AuditPayload;
  onReset: () => void;
}

const AGENT_META: { key: AgentKey; name: string }[] = [
  { key: 'GeospatialTruthAgent', name: 'Geospatial Truth' },
  { key: 'LedgerAuditorAgent', name: 'Ledger Auditor' },
  { key: 'MediaSentinelAgent', name: 'Media Sentinel' },
  { key: 'ReportParserAgent', name: 'Report Parser' },
];

const CLASSIFICATION: Record<string, { label: string; cls: string }> = {
  ALERT: { label: 'Contradicts', cls: 'contradicts' },
  SUCCESS: { label: 'Supports', cls: 'supports' },
  PROCESSING: { label: 'Insufficient', cls: 'insufficient' },
  IDLE: { label: 'Insufficient', cls: 'insufficient' },
};

export function DashboardView({ audit, onReset }: Props) {
  const { global_metrics: g, agent_states } = audit;

  const sources = [
    ...agent_states.MediaSentinelAgent.articles.map((a) => ({
      label: a.source,
      detail: a.headline,
      url: a.url,
    })),
    {
      label: agent_states.GeospatialTruthAgent.metrics.satellite_source,
      detail: 'Tropospheric NO₂ time-series over target polygon',
      url: '#',
    },
    {
      label: 'Internal procurement ledger',
      detail: `${agent_states.LedgerAuditorAgent.rows.length} purchase orders cross-checked`,
      url: '#',
    },
  ];

  return (
    <div className="wz wz--wide gg-fade-in">
      <header className="wz__head wz__head--row">
        <div>
          <span className="wz__eyebrow">Step 4 · Dashboard Layer</span>
          <h1 className="wz__title">Explainable greenwashing-risk verdict</h1>
        </div>
        <div className="wz__head-actions">
          <button className="wz-btn wz-btn--ghost" onClick={() => window.print()}>
            <Download size={15} />
            Export report
          </button>
          <button className="wz-btn wz-btn--ghost" onClick={onReset}>
            <RefreshCw size={15} />
            New audit
          </button>
        </div>
      </header>

      <section className="ev-block">
        <RiskScoreRing metrics={g} phase="complete" />
      </section>

      <div className="dash-grid">
        <div className="gg-card dash-card">
          <div className="gg-card__header">
            <div>
              <div className="gg-card__title">Weighted contribution</div>
              <div className="gg-card__eyebrow">Weighted Integrity Index · sums to 100%</div>
            </div>
          </div>
          <div className="gg-card__body dash-weights">
            {AGENT_META.map(({ key, name }) => {
              const st = agent_states[key];
              const weight = g.agent_weights[key];
              const cl = CLASSIFICATION[st.status] ?? CLASSIFICATION.IDLE;
              const isVeto = key === 'GeospatialTruthAgent';
              return (
                <div key={key} className="dash-weight">
                  <div className="dash-weight__top">
                    <span className="dash-weight__name">
                      {name}
                      {isVeto && <span className="dash-weight__veto">VETO</span>}
                    </span>
                    <span className={`dash-chip dash-chip--${cl.cls}`}>{cl.label}</span>
                  </div>
                  <div className="dash-weight__bar">
                    <span
                      className="dash-weight__weight"
                      style={{ width: fmtPct(weight) }}
                      title={`weight ${fmtPct(weight)}`}
                    />
                    <span
                      className="dash-weight__risk"
                      style={{ width: fmtPct(weight * st.risk_contribution) }}
                      title={`risk contribution ${fmtPct(st.risk_contribution)}`}
                    />
                  </div>
                  <div className="dash-weight__meta">
                    <span>weight {fmtPct(weight)}</span>
                    <span>contradiction {fmtPct(st.risk_contribution)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="gg-card dash-card">
          <div className="gg-card__header">
            <div>
              <div className="gg-card__title">Evidence sources</div>
              <div className="gg-card__eyebrow">Public, traceable references</div>
            </div>
          </div>
          <div className="gg-card__body dash-sources gg-scroll">
            {sources.map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noreferrer" className="dash-source">
                <span className="dash-source__label">
                  {s.label}
                  <ExternalLink size={12} />
                </span>
                <span className="dash-source__detail">{s.detail}</span>
              </a>
            ))}
          </div>
        </div>
      </div>

      <div className="dash-review">
        <ShieldAlert size={20} />
        <div>
          <div className="dash-review__title">Requires human review</div>
          <p className="dash-review__text">
            This is a decision-support risk indicator, not a legal determination. GreenGag
            distinguishes contradiction from insufficient evidence and does not accuse any entity
            of misconduct. A qualified reviewer should examine the linked evidence before acting.
          </p>
        </div>
      </div>
    </div>
  );
}
