import { useAudit } from './hooks/useAudit';
import { SelectionProvider } from './lib/selection';
import { RiskScoreRing } from './components/RiskScoreRing/RiskScoreRing';
import { AgentSwimlane } from './components/AgentSwimlane/AgentSwimlane';
import { PDFViewer } from './components/PDFViewer/PDFViewer';
import { LedgerTimeline } from './components/LedgerTimeline/LedgerTimeline';
import { DiscrepancyCanvas } from './components/DiscrepancyCanvas/DiscrepancyCanvas';
import { MapCanvas } from './components/MapCanvas/MapCanvas';
import { SentimentFeed } from './components/SentimentFeed/SentimentFeed';
import './App.css';

export default function App() {
  const { audit, phase, live, run } = useAudit();
  const { meta } = audit;

  return (
    <SelectionProvider>
      <div className="gg-app">
        <header className="gg-topbar">
          <div className="gg-brand">
            <div className="gg-brand__mark" aria-hidden />
            <div>
              <div className="gg-brand__name">GreenGag</div>
              <div className="gg-brand__tag">Greenwashing Audit Console</div>
            </div>
          </div>

          <div className="gg-target">
            <div className="gg-target__entity">{meta.target_entity}</div>
            <div className="gg-target__project">{meta.project_name}</div>
          </div>

          <div className="gg-runbar">
            <span className="gg-audit-id">{audit.audit_id}</span>
            <button
              className="gg-run-btn"
              onClick={() => run({ preferLive: true })}
              disabled={phase === 'running'}
            >
              {phase === 'running'
                ? live
                  ? 'Streaming…'
                  : 'Auditing…'
                : 'Re-run Audit'}
            </button>
          </div>
        </header>

        <main className="gg-grid">
          {/* Orchestrator master ring — top center. */}
          <section className="gg-grid__ring">
            <RiskScoreRing metrics={audit.global_metrics} phase={phase} />
          </section>

          {/* Live multi-agent swimlanes. */}
          <section className="gg-grid__swimlane">
            <AgentSwimlane states={audit.agent_states} weights={audit.global_metrics.agent_weights} />
          </section>

          {/* XAI evidence row: PDF (reader) + ledger (accountant). */}
          <section className="gg-grid__pdf">
            <PDFViewer state={audit.agent_states.ReportParserAgent} />
          </section>
          <section className="gg-grid__ledger">
            <LedgerTimeline state={audit.agent_states.LedgerAuditorAgent} />
          </section>

          {/* Discrepancy Canvas — animated SVG triangulation linkages. */}
          <section className="gg-grid__canvas">
            <DiscrepancyCanvas audit={audit} />
          </section>

          {/* Geospatial truth + public sentiment. */}
          <section className="gg-grid__map">
            <MapCanvas state={audit.agent_states.GeospatialTruthAgent} meta={meta} />
          </section>
          <section className="gg-grid__feed">
            <SentimentFeed state={audit.agent_states.MediaSentinelAgent} />
          </section>
        </main>

        <footer className="gg-footer">
          <span>
            Weighted Integrity Index · Geospatial truth carries 50% · GeospatialTruthAgent holds veto
          </span>
          <span className="gg-footer__mode">{live ? 'live stream' : 'mock data'}</span>
        </footer>
      </div>
    </SelectionProvider>
  );
}
