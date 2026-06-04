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

export const verdictLabel: Record<FinalVerdict, string> = {
  CLEAR: 'Clear',
  LOW_RISK: 'Low Risk',
  MODERATE_RISK: 'Moderate Risk',
  HIGH_RISK: 'High Risk',
  CRITICAL_RISK_FRAUD_DETECTED: 'Critical — Fraud Detected',
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
