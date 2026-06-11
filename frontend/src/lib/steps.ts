export type WizardStep = 'upload' | 'claims' | 'evidence' | 'dashboard';

export interface StepDef {
  id: WizardStep;
  label: string;
  desc: string;
}

export const STEPS: StepDef[] = [
  { id: 'upload', label: 'Upload Report', desc: 'Ingest ESG / sustainability PDF' },
  { id: 'claims', label: 'Extract Claims', desc: 'Structured claim objects' },
  { id: 'evidence', label: 'Triangulate Evidence', desc: 'Multi-agent verification' },
  { id: 'dashboard', label: 'Risk Verdict', desc: 'Explainable greenwashing score' },
];

export const stepIndex = (s: WizardStep): number => STEPS.findIndex((x) => x.id === s);
