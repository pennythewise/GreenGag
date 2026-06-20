import { useState } from 'react';
import type { AuditMeta, GeospatialTruthState, LayerTimeSeries, SatelliteLayer } from '../../types/audit';
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

const SOURCE_SHORT: Record<string, string> = {
  'Sentinel-5P_TROPOMI': 'Sentinel-5P',
  'ECMWF_ERA5': 'ERA5',
  'Planet_NDVI': 'Planet Labs',
  'GEE_NDVI': 'GEE',
};

function LayerBadge({ layer }: { layer: SatelliteLayer }) {
  return (
    <span className={`mapc__badge ${layer.anomaly_detected ? 'mapc__badge--alert' : 'mapc__badge--ok'}`}>
      {layer.anomaly_detected && <span className="mapc__badge-dot" />}
      {SOURCE_SHORT[layer.source] ?? layer.source} · {layer.parameter}
      {layer.veto && <span className="mapc__badge-veto">VETO</span>}
    </span>
  );
}

function LayerChart({ series }: { series: LayerTimeSeries }) {
  const data = series.points;
  if (!data.length) return <div className="mapc__no-data">No data points</div>;

  const W = 320;
  const H = 150;
  const pad = { l: 28, r: 12, t: 14, b: 22 };
  const max = Math.max(...data.flatMap((d) => [d.claimed, d.observed])) * 1.1;
  const x = (i: number) => pad.l + (i / Math.max(data.length - 1, 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const path = (key: 'claimed' | 'observed') =>
    data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(d[key])}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mapc__chart">
      {[0, 0.5, 1].map((g) => (
        <line
          key={g}
          x1={pad.l} x2={W - pad.r}
          y1={pad.t + g * (H - pad.t - pad.b)}
          y2={pad.t + g * (H - pad.t - pad.b)}
          className="mapc__grid"
        />
      ))}
      <path d={path('claimed')} className="mapc__line mapc__line--claimed" />
      <path d={path('observed')} className="mapc__line mapc__line--observed" />
      <text x={pad.l} y={H - 6} className="mapc__axis">{data[0].date}</text>
      <text x={W - pad.r} y={H - 6} className="mapc__axis" textAnchor="end">{data[data.length - 1].date}</text>
    </svg>
  );
}

function LayerDetail({
  series,
  layer,
}: {
  series: LayerTimeSeries;
  layer: SatelliteLayer;
}) {
  return (
    <div className="mapc__chart-wrap">
      <div className="mapc__chart-head">
        {series.label}
        <span className="mapc__chart-unit">{series.unit}</span>
      </div>
      <LayerChart series={series} />
      <div className="mapc__legend">
        <span><i className="mapc__sw mapc__sw--claimed" /> claimed</span>
        <span><i className="mapc__sw mapc__sw--observed" /> satellite observed</span>
      </div>
      <div className={`mapc__variance ${layer.anomaly_detected ? 'mapc__variance--alert' : ''}`}>
        {layer.anomaly_detected ? (
          <>
            observed variance{' '}
            <strong>+{Math.round(layer.observed_variance_pct * 100)}%</strong>{' '}
            vs. claim · confidence {Math.round(layer.confidence_index * 100)}%
            {layer.veto && <span className="mapc__veto-line"> · VETO ASSERTED</span>}
          </>
        ) : (
          <>
            {layer.parameter} within normal range · confidence {Math.round(layer.confidence_index * 100)}%
          </>
        )}
      </div>
    </div>
  );
}

export function MapCanvas({ state, meta }: { state: GeospatialTruthState; meta: AuditMeta }) {
  const [activeTab, setActiveTab] = useState(0);

  const cols = 5;
  const rows = 5;

  // Match each layer_series to its SatelliteLayer metadata
  const tabs = state.layer_series.map((series) => ({
    series,
    layer: state.metrics.layers.find((l) => l.layer_id === series.layer_id) ?? state.metrics.layers[0],
  }));

  const active = tabs[activeTab] ?? tabs[0];

  return (
    <div className="gg-card mapc">
      <div className="gg-card__header">
        <div>
          <div className="gg-card__title">Geospatial Truth Canvas</div>
          <div className="mapc__badges">
            {state.metrics.layers.map((l) => (
              <LayerBadge key={l.layer_id} layer={l} />
            ))}
            {state.metrics.plume_trajectory_modeled && (
              <span className="mapc__badge mapc__badge--info">HYSPLIT ✓</span>
            )}
            {state.metrics.asset_geofenced && (
              <span className="mapc__badge mapc__badge--info">Geofenced ✓</span>
            )}
          </div>
        </div>
        <div className={`gg-status gg-status--${state.status}`}>
          <span className="gg-status__dot" />
          {state.metrics.veto ? 'VETO' : state.status}
        </div>
      </div>

      {/* Layer tabs */}
      {tabs.length > 1 && (
        <div className="mapc__tabs">
          {tabs.map(({ series, layer }, i) => (
            <button
              key={series.layer_id}
              className={`mapc__tab ${i === activeTab ? 'mapc__tab--active' : ''} ${layer.anomaly_detected ? 'mapc__tab--alert' : ''}`}
              onClick={() => setActiveTab(i)}
            >
              {layer.anomaly_detected && <span className="mapc__badge-dot" />}
              {layer.parameter}
            </button>
          ))}
        </div>
      )}

      <div className="mapc__body">
        {/* Heatmap */}
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
            {meta.target_entity} · {rows}×{cols} raster
          </div>
        </div>

        {/* Active layer chart */}
        {active && (
          <LayerDetail series={active.series} layer={active.layer} />
        )}
      </div>
    </div>
  );
}
