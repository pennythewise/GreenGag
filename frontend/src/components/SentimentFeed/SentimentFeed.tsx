import type { MediaArticle, MediaSentinelState } from '../../types/audit';
import { fmtPct } from '../../lib/format';
import './SentimentFeed.css';

const TAG_LABEL: Record<MediaArticle['tag'], string> = {
  incident: 'Incident',
  ngo: 'NGO',
  community: 'Community',
  news: 'News',
};

function scoreColor(s: number): string {
  if (s >= 0.75) return 'var(--terra)';
  if (s >= 0.5) return 'var(--amber)';
  return 'var(--sage)';
}

export function SentimentFeed({ state }: { state: MediaSentinelState }) {
  return (
    <div className="gg-card sfeed">
      <div className="gg-card__header">
        <div>
          <div className="gg-card__title">Public Sentiment Track</div>
          <div className="gg-card__eyebrow">Media Sentinel · {state.articles.length} scraped sources</div>
        </div>
        <div className={`gg-status gg-status--${state.status}`}>
          <span className="gg-status__dot" />
          {state.status}
        </div>
      </div>

      <div className="sfeed__stream gg-scroll gg-cascade">
        {state.articles.map((a) => (
          <article key={a.id} className="sfeed__card">
            <header className="sfeed__head">
              <span className={`sfeed__tag sfeed__tag--${a.tag}`}>{TAG_LABEL[a.tag]}</span>
              <span className="sfeed__date">{a.published}</span>
            </header>
            <h4 className="sfeed__headline">{a.headline}</h4>
            <p className="sfeed__snippet">{a.snippet}</p>
            <footer className="sfeed__foot">
              <a href={a.url} target="_blank" rel="noreferrer" className="sfeed__source">
                {a.source} ↗
              </a>
              <span className="sfeed__score" title="Reputational contradiction score">
                <span className="sfeed__score-bar">
                  <span
                    className="sfeed__score-fill"
                    style={{ width: fmtPct(a.contradiction_score), background: scoreColor(a.contradiction_score) }}
                  />
                </span>
                <span className="sfeed__score-num" style={{ color: scoreColor(a.contradiction_score) }}>
                  {fmtPct(a.contradiction_score)}
                </span>
              </span>
            </footer>
          </article>
        ))}
      </div>
    </div>
  );
}
