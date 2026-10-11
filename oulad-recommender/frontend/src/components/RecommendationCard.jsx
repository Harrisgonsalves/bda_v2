export default function RecommendationCard({ rec, onOpen, onComplete, onFeedback, busy }) {
  const c = rec.content_score, cf = rec.collab_score;
  const total = c + cf || 1;
  return (
    <article className="rec">
      <div className="rec-head">
        <span className="rank">{rec.rank}</span>
        <div>
          <h3>{rec.title || `Resource ${rec.resource_id}`}</h3>
          <p className="muted small">{rec.activity_type}{rec.week_from != null ? `, from week ${rec.week_from}` : ""}</p>
        </div>
        <div className="score" title="Final hybrid score">{rec.score.toFixed(2)}</div>
      </div>
      <div className="split" title={`Content ${c.toFixed(2)}, collaborative ${cf.toFixed(2)}`}>
        <span className="seg content" style={{ width: `${(c / total) * 100}%` }} />
        <span className="seg collab" style={{ width: `${(cf / total) * 100}%` }} />
      </div>
      <p className="reason">{rec.reason}</p>
      <div className="actions">
        <button className="btn primary sm" disabled={busy} onClick={() => onOpen(rec)}>Open</button>
        <button className="btn sm" disabled={busy} onClick={() => onComplete(rec)}>Mark complete</button>
        <span className="spacer" />
        <button className="btn ghost sm" disabled={busy} onClick={() => onFeedback(rec, true)}>Useful</button>
        <button className="btn ghost sm" disabled={busy} onClick={() => onFeedback(rec, false)}>Not for me</button>
      </div>
    </article>
  );
}
