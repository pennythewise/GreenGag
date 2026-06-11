import { ArrowRight, RotateCcw, Target } from 'lucide-react';
import type { AuditPayload, ExtractedClaim } from '../../types/audit';
import type { RunPhase } from '../../hooks/useAudit';
import { AgentSwimlane } from '../AgentSwimlane/AgentSwimlane';
import { DiscrepancyCanvas } from '../DiscrepancyCanvas/DiscrepancyCanvas';
import { LedgerTimeline } from '../LedgerTimeline/LedgerTimeline';
import { MapCanvas } from '../MapCanvas/MapCanvas';
import { SentimentFeed } from '../SentimentFeed/SentimentFeed';
import './wizard.css';

interface Props {
  audit: AuditPayload;
  phase: RunPhase;
  claim: ExtractedClaim | null;
  onReplay: () => void;
  onProceed: () => void;
}

/**
 * Step 3 — Evidence triangulation. The Report Parser's claim is fanned out to
 * the three evidence agents (live swimlanes), whose findings are linked on the
 * Discrepancy Canvas and detailed in the ledger / geospatial / media surfaces.
 */
export function EvidenceView({ audit, phase, claim, onReplay, onProceed }: Props) {
  const running = phase === 'running';

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
          <button className="wz-btn wz-btn--ghost" onClick={onReplay} disabled={running}>
            <RotateCcw size={15} />
            Replay
          </button>
          <button className="wz-btn wz-btn--primary" onClick={onProceed} disabled={running}>
            {running ? 'Agents verifying…' : 'View risk verdict'}
            {!running && <ArrowRight size={16} />}
          </button>
        </div>
      </header>

      <section className="ev-block">
        <AgentSwimlane states={audit.agent_states} weights={audit.global_metrics.agent_weights} />
      </section>

      <section className="ev-block">
        <DiscrepancyCanvas audit={audit} />
      </section>

      <section className="ev-grid">
        <LedgerTimeline state={audit.agent_states.LedgerAuditorAgent} />
        <MapCanvas state={audit.agent_states.GeospatialTruthAgent} meta={audit.meta} />
      </section>

      <section className="ev-block">
        <SentimentFeed state={audit.agent_states.MediaSentinelAgent} />
      </section>
    </div>
  );
}
