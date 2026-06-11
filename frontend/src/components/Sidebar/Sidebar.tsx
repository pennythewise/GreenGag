import { Upload, FileSearch, Network, Gauge, Check, Lock } from 'lucide-react';
import type { WizardStep } from '../../lib/steps';
import { STEPS } from '../../lib/steps';
import './Sidebar.css';

const ICONS = { upload: Upload, claims: FileSearch, evidence: Network, dashboard: Gauge } as const;

interface Props {
  current: WizardStep;
  /** Highest step the user has unlocked so far. */
  reached: WizardStep;
  onNavigate: (step: WizardStep) => void;
}

/**
 * Vertical 4-step stepper. Forward steps stay locked until their prerequisites
 * are met (governed by `reached`); completed steps are always clickable.
 */
export function Sidebar({ current, reached, onNavigate }: Props) {
  const reachedIdx = STEPS.findIndex((s) => s.id === reached);
  const currentIdx = STEPS.findIndex((s) => s.id === current);

  return (
    <aside className="gg-side">
      <div className="gg-side__brand">
        <div className="gg-side__mark" aria-hidden />
        <div>
          <div className="gg-side__name">GreenGag</div>
          <div className="gg-side__tag">Evidence Triangulation</div>
        </div>
      </div>

      <nav className="gg-side__steps" aria-label="Audit workflow">
        {STEPS.map((step, i) => {
          const Icon = ICONS[step.id];
          const isDone = i < currentIdx;
          const isCurrent = i === currentIdx;
          const isLocked = i > reachedIdx;

          return (
            <button
              key={step.id}
              className={[
                'gg-step',
                isCurrent ? 'is-current' : '',
                isDone ? 'is-done' : '',
                isLocked ? 'is-locked' : '',
              ].join(' ')}
              onClick={() => !isLocked && onNavigate(step.id)}
              disabled={isLocked}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span className="gg-step__rail" aria-hidden>
                <span className="gg-step__node">
                  {isDone ? <Check size={15} /> : isLocked ? <Lock size={13} /> : <Icon size={16} />}
                </span>
                {i < STEPS.length - 1 && <span className="gg-step__line" />}
              </span>
              <span className="gg-step__body">
                <span className="gg-step__no">Step {i + 1}</span>
                <span className="gg-step__label">{step.label}</span>
                <span className="gg-step__desc">{step.desc}</span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="gg-side__foot">
        <div className="gg-side__foot-line">Weighted Integrity Index</div>
        <div className="gg-side__foot-sub">Geospatial truth · 50% · holds veto</div>
      </div>
    </aside>
  );
}
