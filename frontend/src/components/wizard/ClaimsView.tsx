import { ArrowRight, CircleDot, Circle, AlertTriangle } from 'lucide-react';
import type { AuditMeta, ExtractedClaim, ReportParserState } from '../../types/audit';
import { useSelection } from '../../lib/selection';
import { fmtUSD } from '../../lib/format';
import { PDFViewer } from '../audit/PDFViewer/PDFViewer';
import './wizard.css';

interface Props {
  parser: ReportParserState;
  meta: AuditMeta;
  selectedClaimId: string | null;
  onSelect: (id: string) => void;
  onProceed: () => void;
  busy?: boolean;
  error?: string | null;
  documentId?: string | null;
  onRetryExtract?: () => void;
}

/** Builds the structured claim-object fields shown in the inspector panel. */
function structuredFields(claim: ExtractedClaim, meta: AuditMeta) {
  const fields: { k: string; v: string }[] = [];
  if (claim.pillar) fields.push({ k: 'pillar', v: claim.pillar });
  if (claim.claim_type) fields.push({ k: 'claim_type', v: claim.claim_type });
  fields.push({ k: 'entity', v: claim.entity ?? meta.target_entity });
  if (claim.target_value) fields.push({ k: 'target_value', v: claim.target_value });
  if (claim.achieved_value) fields.push({ k: 'achieved_value', v: claim.achieved_value });
  if (claim.claimed_reduction_pct != null)
    fields.push({ k: 'reduction_target', v: `${claim.claimed_reduction_pct}%` });
  if (claim.material_class) fields.push({ k: 'material_class', v: claim.material_class });
  if (claim.stated_spend_usd != null)
    fields.push({ k: 'stated_spend', v: fmtUSD(claim.stated_spend_usd) });
  if (claim.confidence != null)
    fields.push({ k: 'confidence', v: `${Math.round(claim.confidence * 100)}%` });
  fields.push({ k: 'project', v: claim.location ?? meta.project_name });
  return fields;
}

export function ClaimsView({
  parser,
  meta,
  selectedClaimId,
  onSelect,
  onProceed,
  busy,
  error,
  onRetryExtract,
}: Props) {
  const { setActiveClaim } = useSelection();
  const claims = parser.extracted_claims;
  const selected = claims.find((c) => c.id === selectedClaimId) ?? null;

  return (
    <div className="wz wz--wide gg-fade-in">
      <header className="wz__head wz__head--row">
        <div>
          <span className="wz__eyebrow">Step 2 · Claim Intelligence Layer</span>
          <h1 className="wz__title">Extracted ESG claims</h1>
          <p className="wz__lede wz__lede--tight">
            The Report Parser highlighted {claims.length} measurable claims (amber) and normalised
            each into a structured object. Select one claim to triangulate.
          </p>
        </div>
        <button className="wz-btn wz-btn--primary" disabled={!selected} onClick={onProceed}>
          Triangulate evidence
          <ArrowRight size={16} />
        </button>
      </header>

      {busy && (
        <div className="wz-banner">Extracting claims from retrieved report sections…</div>
      )}
      {error && (
        <div className="wz-error">
          {error}
          {onRetryExtract && (
            <button className="wz-btn wz-btn--ghost" onClick={onRetryExtract}>
              Retry extraction
            </button>
          )}
        </div>
      )}

      <div className="claims-grid">
        <div className="claims-grid__pdf">
          <PDFViewer state={parser} />
        </div>

        <div className="claims-grid__list gg-scroll">
          {claims.map((c) => {
            const active = c.id === selectedClaimId;
            return (
              <button
                key={c.id}
                className={`claim-card ${active ? 'is-active' : ''}`}
                onClick={() => {
                  onSelect(c.id);
                  setActiveClaim(c.id);
                }}
                onMouseEnter={() => setActiveClaim(c.id)}
              >
                <div className="claim-card__top">
                  {active ? (
                    <CircleDot size={18} className="claim-card__radio is-on" />
                  ) : (
                    <Circle size={18} className="claim-card__radio" />
                  )}
                  <span className="claim-card__label">{c.label}</span>
                </div>
                <p className="claim-card__raw">“{c.raw_text}”</p>

                {active && (
                  <div className="claim-card__struct gg-fade-in">
                    <div className="claim-card__struct-head">Structured claim object</div>
                    {structuredFields(c, meta).map((f) => (
                      <div key={f.k} className="claim-card__kv">
                        <span className="claim-card__k">{f.k}</span>
                        <span className="claim-card__v">{f.v}</span>
                      </div>
                    ))}
                  </div>
                )}
              </button>
            );
          })}

          <div className="claims-grid__hint">
            <AlertTriangle size={14} />
            Claim extraction identifies what is claimed — it does not verify truth. Verification
            happens in the next step.
          </div>
        </div>
      </div>
    </div>
  );
}
