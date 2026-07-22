export default function TripSummary({ trip, onReset }) {
  if (!trip) return null
  const { summary, route, waypoints } = trip
  return (
    <div className="trip-summary">
      <div className="summary-route">
        <strong>{waypoints?.current?.label}</strong>
        <span className="arrow">→</span>
        <strong>{waypoints?.pickup?.label}</strong>
        <span className="arrow">→</span>
        <strong>{waypoints?.dropoff?.label}</strong>
      </div>
      <div className="summary-meta">
        <span>{route.total_distance_miles.toLocaleString()} mi</span>
        <span>{route.total_drive_hours.toFixed(1)} drive hrs</span>
        <span>{summary.total_days} day{summary.total_days === 1 ? '' : 's'}</span>
        <span>
          Cycle {summary.cycle_used_start.toFixed(1)} → {summary.cycle_used_end.toFixed(1)} hrs
        </span>
        {summary.restarts_taken > 0 && (
          <span className="badge">{summary.restarts_taken} restart{summary.restarts_taken === 1 ? '' : 's'}</span>
        )}
      </div>
      <button type="button" className="btn-ghost" onClick={onReset}>
        New trip
      </button>
    </div>
  )
}
