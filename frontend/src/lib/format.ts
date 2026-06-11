import type { AgentStatus, FinalVerdict } from '../types/audit';

export const fmtUSD = (n: number): string =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n);

export const fmtPct = (ratio: number, digits = 0): string =>
  `${(ratio * 100).toFixed(digits)}%`;

export const statusLabel: Record<AgentStatus, string> = {
  IDLE: 'Idle',
  PROCESSING: 'Processing',
  SUCCESS: 'Verified',
  ALERT: 'Alert',
};

/**
 * Display labels use responsible, non-accusatory wording (proposal §14.6).
 * The top tier keeps PRD severity but is framed as a risk indicator that
 * "requires human review" rather than a fraud accusation.
 */
export const verdictLabel: Record<FinalVerdict, string> = {
  CLEAR: 'Clear',
  LOW_RISK: 'Low Greenwashing Risk',
  MODERATE_RISK: 'Moderate Greenwashing Risk',
  HIGH_RISK: 'High Greenwashing Risk',
  CRITICAL_RISK_FRAUD_DETECTED: 'Critical Greenwashing Risk · Requires Human Review',
};

/** Maps a 0–1 risk score to an accent color along sage → amber → terra. */
export const riskColor = (score: number): string => {
  if (score >= 0.66) return 'var(--terra)';
  if (score >= 0.33) return 'var(--amber)';
  return 'var(--sage)';
};

export const severityColor = (
  severity: 'low' | 'medium' | 'high' | 'critical',
): string =>
  ({
    low: 'var(--sage)',
    medium: 'var(--amber)',
    high: 'var(--terra)',
    critical: 'var(--terra)',
  })[severity];
