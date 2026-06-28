import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, RotateCcw, Target } from 'lucide-react';
import type { AuditPayload, ExtractedClaim } from '../../types/audit';
import type { WeightedVerificationResult } from '../../types/audit';
import { verifyClaim } from '../../lib/documents';
import { MapCanvas } from '../audit/MapCanvas/MapCanvas';
import { WeightedConfidencePanel } from '../audit/WeightedConfidencePanel/WeightedConfidencePanel';
import './wizard.css';

interface Props {
  audit: AuditPayload;
  documentId: string | null;
  claim: ExtractedClaim | null;
  onProceed: () => void;
}

/**
 * Step 3 — Evidence triangulation for one selected claim. The weighted
 * confidence framework scores deterministic evidence layers; Geospatial Truth
 * remains a separate mocked canvas for now.
 */
export function EvidenceView({ audit, documentId, claim, onProceed }: Props) {
  const [result, setResult] = useState<WeightedVerificationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runVerification = useCallback(async () => {
    if (!documentId || !claim) return;
    setBusy(true);
    setError(null);
    try {
      const next = await verifyClaim(documentId, claim.id);
      setResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed.');
    } finally {
      setBusy(false);
    }
  }, [documentId, claim]);

  useEffect(() => {
    setResult(null);
    void runVerification();
  }, [runVerification]);

  return (
    <div className="wz wz--wide gg-fade-in">
      <header className="wz__head wz__head--row">
        <div>
          <span className="wz__eyebrow">Step 3 · Evidence Agent Layer</span>
          <h1 className="wz__title">Multi-agent verification</h1>
          {claim && (
            <p className="wz__lede wz__lede--tight">
              <Target size={14} className="wz__target-icon" />
              Verifying: <strong>“{claim.raw_text}”</strong>
            </p>
          )}
        </div>
        <div className="wz__head-actions">
          <button className="wz-btn wz-btn--ghost" onClick={runVerification} disabled={busy || !claim}>
            <RotateCcw size={15} />
            {busy ? 'Verifying…' : 'Replay verification'}
          </button>
          <button className="wz-btn wz-btn--primary" onClick={onProceed} disabled={busy}>
            View risk verdict
            <ArrowRight size={16} />
          </button>
        </div>
      </header>

      <section className="ev-grid">
        {claim ? (
          <WeightedConfidencePanel
            claim={claim}
            result={result}
            busy={busy}
            error={error}
          />
        ) : (
          <div className="wz-error">Select a claim before triangulating evidence.</div>
        )}
        <MapCanvas state={audit.agent_states.GeospatialTruthAgent} meta={audit.meta} />
      </section>
    </div>
  );
}
