import { useState } from 'react';
import { useAudit } from '../hooks/useAudit';
import { SelectionProvider, useSelection } from '../lib/selection';
import { stepIndex, type WizardStep } from '../lib/steps';
import { Sidebar } from '../components/layout/Sidebar/Sidebar';
import { UploadView } from '../components/wizard/UploadView';
import { ClaimsView } from '../components/wizard/ClaimsView';
import { EvidenceView } from '../components/wizard/EvidenceView';
import { DashboardView } from '../components/wizard/DashboardView';
import './App.css';

function Wizard() {
  const { audit, phase, run } = useAudit();
  const { setActiveClaim, setActiveDiscrepancy } = useSelection();

  const [step, setStep] = useState<WizardStep>('upload');
  const [reached, setReached] = useState<WizardStep>('upload');
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);

  const parser = audit.agent_states.ReportParserAgent;
  const selectedClaim = parser.extracted_claims.find((c) => c.id === selectedClaimId) ?? null;

  /** Unlock up to `target` (never downgrade) and move there. */
  function go(target: WizardStep) {
    setStep(target);
    if (stepIndex(target) > stepIndex(reached)) setReached(target);
  }

  function handleIngest() {
    go('claims');
  }

  function handleTriangulate() {
    if (!selectedClaimId) return;
    go('evidence');
    run(); // staged multi-agent simulation (no backend)
  }

  function handleReset() {
    setActiveClaim(null);
    setActiveDiscrepancy(null);
    setSelectedClaimId(null);
    setReached('upload');
    setStep('upload');
  }

  return (
    <div className="gg-shell">
      <Sidebar current={step} reached={reached} onNavigate={setStep} />

      <main className="gg-main gg-scroll">
        <div className="gg-main__inner">
          {step === 'upload' && <UploadView meta={audit.meta} onIngest={handleIngest} />}

          {step === 'claims' && (
            <ClaimsView
              parser={parser}
              meta={audit.meta}
              selectedClaimId={selectedClaimId}
              onSelect={setSelectedClaimId}
              onProceed={handleTriangulate}
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
