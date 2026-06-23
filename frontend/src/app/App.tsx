import { useCallback, useState } from 'react';
import { useAudit } from '../hooks/useAudit';
import { SelectionProvider, useSelection } from '../lib/selection';
import { stepIndex, type WizardStep } from '../lib/steps';
import {
  extractClaims,
  ingestDocument,
  ingestSampleReport,
} from '../lib/documents';
import type { AuditPayload, ReportParserState } from '../types/audit';
import { Sidebar } from '../components/layout/Sidebar/Sidebar';
import { UploadView } from '../components/wizard/UploadView';
import { ClaimsView } from '../components/wizard/ClaimsView';
import { EvidenceView } from '../components/wizard/EvidenceView';
import { DashboardView } from '../components/wizard/DashboardView';
import './App.css';

function Wizard() {
  const { audit, phase, run, setAudit } = useAudit();
  const { setActiveClaim, setActiveDiscrepancy } = useSelection();

  const [step, setStep] = useState<WizardStep>('upload');
  const [reached, setReached] = useState<WizardStep>('upload');
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [ingestBusy, setIngestBusy] = useState(false);
  const [extractBusy, setExtractBusy] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const parser = audit.agent_states.ReportParserAgent;
  const selectedClaim = parser.extracted_claims.find((c) => c.id === selectedClaimId) ?? null;

  function go(target: WizardStep) {
    setStep(target);
    if (stepIndex(target) > stepIndex(reached)) setReached(target);
  }

  const applyParserState = useCallback(
    (nextParser: ReportParserState) => {
      setAudit((prev: AuditPayload) => ({
        ...prev,
        agent_states: {
          ...prev.agent_states,
          ReportParserAgent: nextParser,
        },
      }));
    },
    [setAudit],
  );

  async function runExtract(docId: string) {
    setExtractBusy(true);
    setPipelineError(null);
    try {
      const result = await extractClaims(docId);
      applyParserState(result.report_parser);
      if (result.claims.length > 0) setSelectedClaimId(result.claims[0].id);
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : 'Extraction failed.');
      throw err;
    } finally {
      setExtractBusy(false);
    }
  }

  async function handleIngest(input: { file?: File; sample?: boolean }) {
    setIngestBusy(true);
    setPipelineError(null);
    try {
      const ingest = input.sample
        ? await ingestSampleReport()
        : input.file
          ? await ingestDocument(input.file)
          : null;
      if (!ingest) return;

      setDocumentId(ingest.document_id);
      go('claims');

      await runExtract(ingest.document_id);
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : 'Ingest failed.');
    } finally {
      setIngestBusy(false);
    }
  }

  function handleTriangulate() {
    if (!selectedClaimId) return;
    go('evidence');
    run();
  }

  function handleReset() {
    setActiveClaim(null);
    setActiveDiscrepancy(null);
    setSelectedClaimId(null);
    setDocumentId(null);
    setPipelineError(null);
    setReached('upload');
    setStep('upload');
  }

  return (
    <div className="gg-shell">
      <Sidebar current={step} reached={reached} onNavigate={setStep} />

      <main className="gg-main gg-scroll">
        <div className="gg-main__inner">
          {step === 'upload' && (
            <UploadView
              meta={audit.meta}
              onIngest={handleIngest}
              busy={ingestBusy || extractBusy}
              error={pipelineError}
            />
          )}

          {step === 'claims' && (
            <ClaimsView
              parser={parser}
              meta={audit.meta}
              selectedClaimId={selectedClaimId}
              onSelect={setSelectedClaimId}
              onProceed={handleTriangulate}
              busy={extractBusy}
              error={pipelineError}
              documentId={documentId}
              onRetryExtract={
                documentId ? () => void runExtract(documentId) : undefined
              }
            />
          )}

          {step === 'evidence' && (
            <EvidenceView
              audit={audit}
              phase={phase}
              claim={selectedClaim}
              onReplay={run}
              onProceed={() => go('dashboard')}
            />
          )}

          {step === 'dashboard' && <DashboardView audit={audit} onReset={handleReset} />}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <SelectionProvider>
      <Wizard />
    </SelectionProvider>
  );
}
