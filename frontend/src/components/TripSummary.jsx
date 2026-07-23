export default function TripSummary({ trip, onReset }) {
  if (!trip) return null
  const { summary, route, waypoints } = trip

  const legs = [
    waypoints?.current?.label,
    waypoints?.pickup?.label,
    waypoints?.dropoff?.label,
  ].filter(Boolean)

  return (
    <div className="trip-summary reveal">
      <div className="summary-main">
        <p className="summary-kicker">Planned route</p>
        <div className="summary-route" aria-label="Trip stops">
          {legs.map((label, i) => (
            <span key={`${label}-${i}`} className="summary-leg">
              {i > 0 && <span className="arrow" aria-hidden="true">→</span>}
              <strong>{label}</strong>
            </span>
          ))}
        </div>
      </div>

      <dl className="summary-meta">
        <div>
          <dt>Distance</dt>
          <dd>{route.total_distance_miles.toLocaleString()} mi</dd>
        </div>
        <div>
          <dt>Drive time</dt>
          <dd>{route.total_drive_hours.toFixed(1)} hrs</dd>
        </div>
        <div>
          <dt>Log days</dt>
          <dd>{summary.total_days}</dd>
        </div>
        <div>
          <dt>Cycle</dt>
          <dd>
            {summary.cycle_used_start.toFixed(1)} → {summary.cycle_used_end.toFixed(1)}
          </dd>
        </div>
        {summary.restarts_taken > 0 && (
          <div className="meta-badge">
            <dt>Restart</dt>
            <dd>
              {summary.restarts_taken}× 34h
            </dd>
          </div>
        )}
      </dl>

      <button type="button" className="btn-ghost summary-reset" onClick={onReset}>
        New trip
      </button>
    </div>
  )
}
