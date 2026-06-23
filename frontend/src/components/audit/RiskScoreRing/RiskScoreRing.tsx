import type { GlobalMetrics } from '../../../types/audit';
import { fmtPct, riskColor, verdictLabel } from '../../../lib/format';
import type { RunPhase } from '../../../hooks/useAudit';
import './RiskScoreRing.css';

const R = 92;
const CIRC = 2 * Math.PI * R;

interface Props {
  metrics: GlobalMetrics;
  phase: RunPhase;
}

/**
 * Orchestrator Agent rendered as the master status ring (PRD §3.1 Agent 1):
 * aggregate Global Greenwashing Risk Score + Executive Verdict Summary.
 */
export function RiskScoreRing({ metrics, phase }: Props) {
  const score = metrics.weighted_risk_score;
  const color = riskColor(score);
  const dash = CIRC * score;

  return (
    <div className="gg-card gg-card--raised rsr">
      <div className="rsr__dial">
        <svg viewBox="0 0 220 220" className="rsr__svg" role="img" aria-label="Global risk score">
          <circle cx="110" cy="110" r={R} className="rsr__track" />
          <circle
            cx="110"
            cy="110"
            r={R}
            className="rsr__progress"
            stroke={color}
            strokeDasharray={`${dash} ${CIRC - dash}`}
            transform="rotate(-90 110 110)"
          />
          {/* tick marks */}
          {Array.from({ length: 40 }).map((_, i) => {
            const a = (i / 40) * 2 * Math.PI;
            const inner = 74;
            const outer = i % 5 === 0 ? 66 : 70;
            return (
              <line
                key={i}
                x1={110 + Math.cos(a) * inner}
                y1={110 + Math.sin(a) * inner}
                x2={110 + Math.cos(a) * outer}
                y2={110 + Math.sin(a) * outer}
                className="rsr__tick"
              />
            );
          })}
        </svg>
        <div className="rsr__center">
          <div className="rsr__score" style={{ color }}>
            {fmtPct(score)}
          </div>
          <div className="rsr__score-label">Greenwashing Risk</div>
          {phase === 'running' && <div className="rsr__live">compiling index…</div>}
        </div>
      </div>

      <div className="rsr__verdict">
        <div className="gg-card__eyebrow">Executive Verdict</div>
        <div
          className="rsr__verdict-tag"
          style={{ color, background: 'color-mix(in srgb, ' + color + ' 12%, transparent)' }}
        >
          {verdictLabel[metrics.final_verdict]}
        </div>
        <p className="rsr__summary">{metrics.executive_summary}</p>
        <div className="rsr__meta">
          <div className="rsr__meta-item">
            <span className="rsr__meta-num">{fmtPct(metrics.confidence_score)}</span>
            <span className="rsr__meta-cap">Confidence</span>
          </div>
          <div className="rsr__meta-item">
            <span className="rsr__meta-num">{fmtPct(metrics.agent_weights.GeospatialTruthAgent)}</span>
            <span className="rsr__meta-cap">Geospatial weight</span>
          </div>
          <div className="rsr__meta-item">
            <span className="rsr__meta-num rsr__veto">VETO</span>
            <span className="rsr__meta-cap">Truth agent authority</span>
          </div>
        </div>
      </div>
    </div>
  );
}
