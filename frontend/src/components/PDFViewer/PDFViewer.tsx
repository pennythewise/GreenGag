import type { ReportParserState } from '../../types/audit';
import { useSelection } from '../../lib/selection';
import { fmtPct } from '../../lib/format';
import './PDFViewer.css';

/**
 * Agent 2 XAI surface: interactive ESG PDF viewer. Extracted claims are
 * highlighted in light amber; clicking one co-selects the linked ledger row
 * and discrepancy across the dashboard.
 */
export function PDFViewer({ state }: { state: ReportParserState }) {
  const { activeClaimId, setActiveClaim } = useSelection();
  const claimById = Object.fromEntries(state.extracted_claims.map((c) => [c.id, c]));

  return (
    <div className="gg-card pdfv">
      <div className="gg-card__header">
        <div>
          <div className="gg-card__title">ESG Report Viewer</div>
          <div className="gg-card__eyebrow">Report Parser · {state.extracted_claims.length} claims extracted</div>
        </div>
        <div className={`gg-status gg-status--${state.status}`}>
          <span className="gg-status__dot" />
          {state.status}
        </div>
      </div>

      <div className="pdfv__doc-title">{state.document.title}</div>

      <div className="pdfv__pages gg-scroll">
        {state.document.pages.map((page) => (
          <article key={page.page} className="pdfv__page">
            <header className="pdfv__page-head">
              <span className="pdfv__page-no">p.{page.page}</span>
              <h4 className="pdfv__page-heading">{page.heading}</h4>
            </header>
            {page.blocks.map((block) => {
              const claim = block.claim_id ? claimById[block.claim_id] : undefined;
              const isClaim = Boolean(claim);
              const isActive = claim && activeClaimId === claim.id;
              return (
                <p
                  key={block.id}
                  className={[
                    'pdfv__block',
                    isClaim ? 'pdfv__block--claim' : '',
                    isActive ? 'pdfv__block--active' : '',
                  ].join(' ')}
                  onClick={() => claim && setActiveClaim(isActive ? null : claim.id)}
                  onMouseEnter={() => claim && setActiveClaim(claim.id)}
                  title={isClaim ? 'Extracted claim — click to trace' : undefined}
                >
                  {block.text}
                  {isClaim && <span className="pdfv__claim-tag">{claim!.label}</span>}
                </p>
              );
            })}
          </article>
        ))}
      </div>

      <div className="pdfv__legend">
        <span className="pdfv__swatch" /> highlighted = extracted claim
        <span className="pdfv__contrib">risk contribution {fmtPct(state.risk_contribution)}</span>
      </div>
    </div>
  );
}
