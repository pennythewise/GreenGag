import type { AuditMeta, GeospatialTruthState } from '../../../types/audit';
import './MapCanvas.css';

/** Sage → amber → terra ramp for the gas-density heatmap. */
function heatColor(t: number): string {
  if (t < 0.5) {
    const k = t / 0.5;
    return `rgb(${Math.round(91 + k * 141)}, ${Math.round(138 + k * 55)}, ${Math.round(114 - k * 2)})`;
  }
  const k = (t - 0.5) / 0.5;
  return `rgb(${Math.round(232 - k * 39)}, ${Math.round(193 - k * 92)}, ${Math.round(112 - k * 38)})`;
}

function TimeSeries({ state }: { state: GeospatialTruthState }) {
  const data = state.time_series;
  const W = 320;
  const H = 150;
  const pad = { l: 28, r: 12, t: 14, b: 22 };
  const max = Math.max(...data.flatMap((d) => [d.claimed, d.observed])) * 1.1;
  const x = (i: number) => pad.l + (i / (data.length - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const path = (key: 'claimed' | 'observed') =>
    data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(d[key])}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mapc__chart">
      {[0, 0.5, 1].map((g) => (
        <line key={g} x1={pad.l} x2={W - pad.r} y1={pad.t + g * (H - pad.t - pad.b)} y2={pad.t + g * (H - pad.t - pad.b)} className="mapc__grid" />
      ))}
      {/* claimed: the declining promise */}
      <path d={path('claimed')} className="mapc__line mapc__line--claimed" />
      {/* observed: the satellite flatline */}
      <path d={path('observed')} className="mapc__line mapc__line--observed" />
      <text x={pad.l} y={H - 6} className="mapc__axis">{data[0].date}</text>
      <text x={W - pad.r} y={H - 6} className="mapc__axis" textAnchor="end">{data[data.length - 1].date}</text>
    </svg>
  );
}

export function MapCanvas({ state }: { state: GeospatialTruthState; meta: AuditMeta }) {
  const cols = 5;
  const rows = 5;

  return (
    <div className="gg-card mapc">
      <div className="gg-card__header">
        <div>
          <div className="gg-card__title">Geospatial Truth Canvas</div>
          <div className="gg-card__eyebrow">{state.metrics.satellite_source} · {state.unit}</div>
        </div>
        <div className={`gg-status gg-status--${state.status}`}>
          <span className="gg-status__dot" />
          {state.metrics.veto ? 'VETO' : state.status}
        </div>
      </div>

      <div className="mapc__body">
        <div className="mapc__map">
          <div className="mapc__heat" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
            {state.heatmap.map((px, i) => (
              <span
                key={i}
                className="mapc__cell"
                style={{ background: heatColor(px.intensity), opacity: 0.35 + px.intensity * 0.6 }}
                title={`intensity ${px.intensity}`}
              />
            ))}
          </div>
          <svg className="mapc__poly" viewBox="0 0 100 100" preserveAspectRatio="none">
            <polygon points="6,6 94,6 94,94 6,94" className="mapc__poly-shape" />
          </svg>
          <div className="mapc__map-cap">
            target polygon · {rows}×{cols} raster · KL Central
          </div>
        </div>

        <div className="mapc__chart-wrap">
          <div className="mapc__chart-head">Claimed vs. Observed</div>
          <TimeSeries state={state} />
          <div className="mapc__legend">
            <span><i className="mapc__sw mapc__sw--claimed" /> claimed reduction</span>
            <span><i className="mapc__sw mapc__sw--observed" /> satellite observed</span>
          </div>
          <div className="mapc__variance">
            observed variance{' '}
            <strong>+{Math.round(state.metrics.observed_gas_variance_percentage * 100)}%</strong>{' '}
            vs. claim · confidence {Math.round(state.metrics.confidence_index * 100)}%
          </div>
        </div>
      </div>
    </div>
  );
}
