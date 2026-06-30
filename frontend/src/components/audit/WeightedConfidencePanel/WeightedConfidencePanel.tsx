import { AlertTriangle, CheckCircle2, ChevronDown, FileSearch } from 'lucide-react';
import type {
  EvidenceLayerScore,
  ExtractedClaim,
  WeightedVerificationResult,
} from '../../../types/audit';
import './WeightedConfidencePanel.css';

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function truncate(text: string, max = 180): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max)}…`;
}

function scoreTone(score: number): string {
  if (score >= 0.75) return 'wc-layer__score--high';
  if (score >= 0.5) return 'wc-layer__score--mid';
  return 'wc-layer__score--low';
}

function EvidenceLayerCard({ layer }: { layer: EvidenceLayerScore }) {
  return (
    <article className={`wc-layer${layer.contradiction ? ' wc-layer--alert' : ''}`}>
      <div className="wc-layer__top">
        <div className="wc-layer__meta">
          <h3>{layer.label}</h3>
          <span className="wc-layer__weight">Weight {pct(layer.weight)}</span>
        </div>
        <div className={`wc-layer__score ${scoreTone(layer.score)}`}>
          <strong>{pct(layer.score)}</strong>
          <span>+{pct(layer.weighted_score)}</span>
        </div>
      </div>

      <div className="wc-bar" aria-hidden="true">
        <span style={{ width: pct(layer.score) }} />
      </div>

      <p className="wc-layer__summary">{truncate(layer.rationale, 220)}</p>

      {layer.evidence_snippets.length > 0 && (
        <details className="wc-layer__details">
          <summary>
            <ChevronDown size={14} />
            Evidence ({layer.evidence_snippets.length})
          </summary>
          <ul className="wc-snippets">
            {layer.evidence_snippets.map((snippet, idx) => (
              <li key={`${layer.layer_key}-${idx}`}>{truncate(snippet, 280)}</li>
            ))}
          </ul>
        </details>
      )}

      {layer.sources.length > 0 && (
        <div className="wc-layer__sources">
          {layer.sources.slice(0, 3).map((source) => (
            <span key={source}>{truncate(source, 48)}</span>
          ))}
          {layer.sources.length > 3 && (
            <span className="wc-layer__sources-more">+{layer.sources.length - 3} more</span>
          )}
        </div>
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
  );
}

interface Props {
  claim: ExtractedClaim;
  result: WeightedVerificationResult | null;
  busy?: boolean;
  error?: string | null;
}

export function WeightedConfidencePanel({ claim, result, busy, error }: Props) {
  const layers = result?.layer_scores ?? [];
  const coreLayers = layers.filter((l) => l.layer_key !== 'industry_benchmark');

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
          <p>&ldquo;{truncate(claim.raw_text, 320)}&rdquo;</p>
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

      {coreLayers.length > 0 && (
        <>
          <div className="wc-breakdown">
            <div className="wc-breakdown__head">Score breakdown</div>
            <table className="wc-breakdown__table">
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>Weight</th>
                  <th>Score</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {coreLayers.map((layer) => (
                  <tr key={layer.layer_key}>
                    <td>{layer.label}</td>
                    <td>{pct(layer.weight)}</td>
                    <td>{pct(layer.score)}</td>
                    <td className="wc-breakdown__contrib">{pct(layer.weighted_score)}</td>
                  </tr>
                ))}
              </tbody>
              {result && (
                <tfoot>
                  <tr>
                    <td colSpan={3}><strong>Overall weighted score</strong></td>
                    <td className="wc-breakdown__contrib"><strong>{pct(result.overall_score)}</strong></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>

          <div className="wc-layers">
            {coreLayers.map((layer) => (
              <EvidenceLayerCard key={layer.layer_key} layer={layer} />
            ))}
          </div>
        </>
      )}

      {result && (
        <div className="wc-trail">
          <CheckCircle2 size={15} />
          <span>{result.rationale_trail[0] ?? 'Verification run completed.'}</span>
        </div>
      )}
    </section>
  );
}

export function getIndustryBenchmarkLayer(
  result: WeightedVerificationResult | null,
): EvidenceLayerScore | undefined {
  return result?.layer_scores.find((l) => l.layer_key === 'industry_benchmark');
}
