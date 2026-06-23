import type { LedgerAuditorState } from '../../../types/audit';
import { useSelection } from '../../../lib/selection';
import { fmtPct, fmtUSD } from '../../../lib/format';
import './LedgerTimeline.css';

/**
 * Agent 3 XAI surface: structured ledger timeline. Green vs. standard spend
 * split exposes the bait-and-switch; clicking a flagged invoice traces to the
 * ESG claim it contradicts (selection co-highlights the PDF block).
 */
export function LedgerTimeline({ state }: { state: LedgerAuditorState }) {
  const { activeClaimId, setActiveClaim } = useSelection();
  const m = state.extracted_metrics;
  const total = m.verified_green_spend_usd + m.unverified_standard_spend_usd;
  const greenPct = total > 0 ? m.verified_green_spend_usd / total : 0;

  return (
    <div className="gg-card ledg">
      <div className="gg-card__header">
        <div>
          <div className="gg-card__title">Ledger Timeline</div>
          <div className="gg-card__eyebrow">Ledger Auditor · procurement cross-check</div>
        </div>
        <div className={`gg-status gg-status--${state.status}`}>
          <span className="gg-status__dot" />
          {state.status}
        </div>
      </div>

      <div className="ledg__split">
        <div className="ledg__split-bar">
          <div className="ledg__split-green" style={{ width: fmtPct(greenPct, 1) }} />
          <div className="ledg__split-std" style={{ width: fmtPct(1 - greenPct, 1) }} />
        </div>
        <div className="ledg__split-legend">
          <span>
            <i className="ledg__dot ledg__dot--green" /> Verified green {fmtUSD(m.verified_green_spend_usd)}
          </span>
          <span>
            <i className="ledg__dot ledg__dot--std" /> Standard / unverified {fmtUSD(m.unverified_standard_spend_usd)}
          </span>
          <span className="ledg__ratio">green ratio {fmtPct(m.green_ratio)}</span>
        </div>
      </div>

      <div className="ledg__table gg-scroll">
        <div className="ledg__row ledg__row--head">
          <span>Invoice</span>
          <span>Vendor / Material</span>
          <span className="ledg__amt">Amount</span>
          <span />
        </div>
        {state.rows.map((row) => {
          const active = row.linked_claim_id && activeClaimId === row.linked_claim_id;
          return (
            <button
              key={row.id}
              className={[
                'ledg__row',
                row.flagged ? 'ledg__row--flagged' : '',
                active ? 'ledg__row--active' : '',
              ].join(' ')}
              onClick={() =>
                row.linked_claim_id &&
                setActiveClaim(active ? null : row.linked_claim_id)
              }
              disabled={!row.linked_claim_id}
            >
              <span className="ledg__inv">
                <span className="ledg__inv-id">{row.invoice_id}</span>
                <span className="ledg__inv-date">{row.date}</span>
              </span>
              <span className="ledg__vendor">
                <span className="ledg__vendor-name">{row.vendor}</span>
                <span className="ledg__material">{row.material}</span>
                {row.note && active && <span className="ledg__note gg-fade-in">↳ {row.note}</span>}
              </span>
              <span className={`ledg__amt ledg__amt--${row.category}`}>{fmtUSD(row.amount_usd)}</span>
              <span className="ledg__flag">
                {row.flagged ? (
                  <span className="ledg__flag-tag">trace ↗</span>
                ) : (
                  <span className="ledg__ok">✓</span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
