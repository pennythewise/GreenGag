import { useCallback, useEffect, useRef, useState } from 'react';
import type { AgentKey, AgentStatus, AuditPayload, BaseAgentState } from '../types/audit';
import { MOCK_AUDIT } from '../mocks/auditPayload';

export type RunPhase = 'ready' | 'running' | 'complete';

const AGENT_ORDER: AgentKey[] = [
  'ReportParserAgent',
  'LedgerAuditorAgent',
  'MediaSentinelAgent',
  'GeospatialTruthAgent',
];

const deepClone = <T,>(v: T): T =>
  typeof structuredClone === 'function'
    ? structuredClone(v)
    : (JSON.parse(JSON.stringify(v)) as T);

/** Reset every agent to IDLE / zero progress and blank the global verdict. */
function blankState(base: AuditPayload): AuditPayload {
  const next = deepClone(base);
  for (const key of AGENT_ORDER) {
    const agent = next.agent_states[key];
    agent.status = 'IDLE';
    agent.progress = 0;
  }
  next.global_metrics = {
    ...next.global_metrics,
    weighted_risk_score: 0,
    confidence_score: 0,
    final_verdict: 'CLEAR',
    executive_summary: 'Awaiting agent findings…',
  };
  return next;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Audit data source.
 *
 * - Live: opens an EventSource to the FastAPI SSE stream when reachable.
 * - Mock: replays MOCK_AUDIT as a staggered cascade so swimlane cards animate
 *   IDLE → PROCESSING → SUCCESS/ALERT and the orchestrator ring fills in.
 */
export function useAudit() {
  const [audit, setAudit] = useState<AuditPayload>(() => MOCK_AUDIT);
  const [phase, setPhase] = useState<RunPhase>('complete');
  const [live, setLive] = useState(false);
  const cancelled = useRef(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      cancelled.current = true;
      esRef.current?.close();
    };
  }, []);

  const simulate = useCallback(async () => {
    cancelled.current = false;
    setPhase('running');
    const working = blankState(MOCK_AUDIT);
    setAudit(deepClone(working));

    for (const key of AGENT_ORDER) {
      if (cancelled.current) return;
      const finalAgent = MOCK_AUDIT.agent_states[key];

      // PROCESSING with a climbing progress ring.
      working.agent_states[key].status = 'PROCESSING';
      for (let p = 0.15; p <= 1.0001; p += 0.28) {
        if (cancelled.current) return;
        working.agent_states[key].progress = Math.min(1, p);
        setAudit(deepClone(working));
        await delay(160);
      }

      // Settle into the agent's final status + findings.
      (working.agent_states as Record<AgentKey, BaseAgentState>)[key] = deepClone(finalAgent);
      setAudit(deepClone(working));
      await delay(220);
    }

    // Orchestrator compiles the weighted index last.
    if (cancelled.current) return;
    working.global_metrics = deepClone(MOCK_AUDIT.global_metrics);
    setAudit(deepClone(working));
    setPhase('complete');
  }, []);

  const streamLive = useCallback((): boolean => {
    if (typeof EventSource === 'undefined') return false;
    try {
      const es = new EventSource('/api/audit/stream');
      esRef.current = es;
      setPhase('running');
      setLive(true);

      es.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.payload) setAudit(data.payload as AuditPayload);
          if (data.type === 'complete') {
            setPhase('complete');
            es.close();
          }
        } catch {
          /* ignore keep-alive / malformed frames */
        }
      };
      es.onerror = () => {
        // Backend unavailable — fall back to local simulation.
        es.close();
        setLive(false);
        void simulate();
      };
      return true;
    } catch {
      return false;
    }
  }, [simulate]);

  const run = useCallback(
    (opts?: { preferLive?: boolean }) => {
      esRef.current?.close();
      if (opts?.preferLive && streamLive()) return;
      void simulate();
    },
    [simulate, streamLive],
  );

  const agentStatuses = AGENT_ORDER.reduce<Record<AgentKey, AgentStatus>>(
    (acc, k) => {
      acc[k] = audit.agent_states[k].status;
      return acc;
    },
    {} as Record<AgentKey, AgentStatus>,
  );

  return { audit, phase, live, run, agentStatuses, agentOrder: AGENT_ORDER };
}
