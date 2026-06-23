import { useState } from 'react';
import type { AgentKey, AgentStates, AgentStatus, BaseAgentState } from '../../../types/audit';
import { fmtPct, statusLabel } from '../../../lib/format';
import './AgentSwimlane.css';

const AGENTS: { key: AgentKey; name: string; role: string }[] = [
  { key: 'ReportParserAgent', name: 'Report Parser', role: 'The Reader' },
  { key: 'LedgerAuditorAgent', name: 'Ledger Auditor', role: 'The Accountant' },
  { key: 'MediaSentinelAgent', name: 'Media Sentinel', role: 'The Watchdog' },
  { key: 'GeospatialTruthAgent', name: 'Geospatial Truth', role: 'The Juror' },
];

const PR = 18;
const PC = 2 * Math.PI * PR;

function ProgressRing({ progress, status }: { progress: number; status: AgentStatus }) {
  const color =
    status === 'ALERT'
      ? 'var(--status-alert)'
      : status === 'SUCCESS'
        ? 'var(--status-success)'
        : status === 'PROCESSING'
          ? 'var(--status-processing)'
          : 'var(--status-idle)';
  return (
    <svg viewBox="0 0 44 44" className="asw__ring" aria-hidden>
      <circle cx="22" cy="22" r={PR} className="asw__ring-track" />
      <circle
        cx="22"
        cy="22"
        r={PR}
        className="asw__ring-fill"
        stroke={color}
        strokeDasharray={`${PC * progress} ${PC}`}
        transform="rotate(-90 22 22)"
      />
    </svg>
  );
}

function ThoughtLog({ trail, open }: { trail: string[]; open: boolean }) {
  if (!open) return null;
  return (
    <div className="asw__log gg-scroll gg-fade-in">
      <div className="asw__log-head">rationale_trail</div>
      {trail.length === 0 && <div className="asw__log-empty">awaiting reasoning…</div>}
      {trail.map((line, i) => (
        <div key={i} className="asw__log-line">
          <span className="asw__log-idx">{String(i + 1).padStart(2, '0')}</span>
          <span>{line}</span>
        </div>
      ))}
    </div>
  );
}

function AgentCard({
  name,
  role,
  weight,
  state,
}: {
  name: string;
  role: string;
  weight: number;
  state: BaseAgentState;
}) {
  const [open, setOpen] = useState(true);
  const isVeto = role === 'The Juror';

  return (
    <div className={`gg-card asw__card asw__card--${state.status}`}>
      <div className="asw__top">
        <ProgressRing progress={state.progress} status={state.status} />
        <div className="asw__id">
          <div className="asw__name">{name}</div>
          <div className="asw__role">
            {role}
            {isVeto && <span className="asw__veto-badge">veto</span>}
          </div>
        </div>
      </div>

      <div className={`gg-status gg-status--${state.status} asw__status`}>
        <span className="gg-status__dot" />
        {statusLabel[state.status]}
      </div>

      <div className="asw__tool">
        <span className="asw__tool-cap">tool</span>
        <code>{state.active_tool ?? '—'}</code>
      </div>

      <div className="asw__metrics">
        <div>
          <span className="asw__metric-num">{fmtPct(state.risk_contribution)}</span>
          <span className="asw__metric-cap">risk</span>
        </div>
        <div>
          <span className="asw__metric-num">{fmtPct(weight)}</span>
          <span className="asw__metric-cap">weight</span>
        </div>
      </div>

      <button className="asw__toggle" onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide' : 'Show'} thought log
      </button>
      <ThoughtLog trail={state.rationale_trail} open={open} />
    </div>
  );
}

export function AgentSwimlane({
  states,
  weights,
}: {
  states: AgentStates;
  weights: Record<AgentKey, number>;
}) {
  return (
    <div>
      <div className="asw__header">
        <h2 className="gg-card__title">Live Agent Swimlanes</h2>
        <span className="gg-card__eyebrow">parallel multi-agent execution</span>
      </div>
      <div className="asw__lanes gg-cascade">
        {AGENTS.map((a) => (
          <AgentCard
            key={a.key}
            name={a.name}
            role={a.role}
            weight={weights[a.key]}
            state={states[a.key]}
          />
        ))}
      </div>
    </div>
  );
}
