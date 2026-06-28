import { AlertTriangle, CheckCircle2, FileSearch } from 'lucide-react';
import type { ExtractedClaim, WeightedVerificationResult } from '../../../types/audit';
import './WeightedConfidencePanel.css';

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

interface Props {
  claim: ExtractedClaim;
  result: WeightedVerificationResult | null;
  busy?: boolean;
  error?: string | null;
}

export function WeightedConfidencePanel({ claim, result, busy, error }: Props) {
  return (
    <section className="wc-panel gg-card">
      <div className="wc-panel__head">
        <div>
          <div className="gg-card__eyebrow">Weighted Confidence Framework</div>
          <div className="gg-card__title">Selected-claim verification</div>
        </div>
        <div className="wc-score">
          <span className="wc-score__value">{result ? pct(result.overall_score) : '—'}</span>
          <span className="wc-score__label">weighted score</span>
        </div>
      </div>

      <div className="wc-claim">
        <FileSearch size={16} />
        <div>
          <strong>{claim.label}</strong>
          <p>“{claim.raw_text}”</p>
        </div>
      </div>

      {busy && <div className="wc-muted">Scoring evidence layers…</div>}
      {error && (
        <div className="wc-error">
          <AlertTriangle size={15} />
          {error}
        </div>
      )}

      {result?.contradiction_flag && (
        <div className="wc-warning">
          <AlertTriangle size={15} />
          {result.score_cap_applied
            ? `Contradiction found. Score capped at ${pct(result.overall_score)} from ${pct(result.uncapped_score ?? result.overall_score)}.`
            : 'Credible contradiction terms were found. The score is shown without override.'}
        </div>
      )}

      <div className="wc-layers">
        {(result?.layer_scores ?? []).map((layer) => (
          <article key={layer.layer_key} className="wc-layer">
            <div className="wc-layer__top">
              <div>
                <h3>{layer.label}</h3>
                <span>Weight {pct(layer.weight)}</span>
              </div>
              <div className="wc-layer__score">
                <strong>{pct(layer.score)}</strong>
                <span>adds {pct(layer.weighted_score)}</span>
              </div>
            </div>
            <div className="wc-bar" aria-hidden="true">
              <span style={{ width: pct(layer.score) }} />
            </div>
            <p className="wc-layer__rationale">{layer.rationale}</p>
            {layer.sources.length > 0 && (
              <div className="wc-layer__sources">
                {layer.sources.map((source) => (
                  <span key={source}>{source}</span>
                ))}
              </div>
            )}
            {layer.evidence_snippets.length > 0 && (
              <ul className="wc-snippets">
                {layer.evidence_snippets.map((snippet, idx) => (
                  <li key={`${layer.layer_key}-${idx}`}>{snippet}</li>
                ))}
              </ul>
            )}
            {layer.missing_evidence && (
              <div className="wc-missing">
                <AlertTriangle size={13} />
                Missing or mocked evidence source
              </div>
            )}
            {layer.contradiction && (
              <div className="wc-missing wc-missing--contradiction">
                <AlertTriangle size={13} />
                Contradiction evidence flagged
              </div>
            )}
          </article>
        ))}
      </div>

      {result && (
        <div className="wc-trail">
          <CheckCircle2 size={15} />
          <span>{result.rationale_trail[0] ?? 'Verification run completed.'}</span>
        </div>
      )}
    </section>
  );
}
