const statusLabel = {
  OFF: 'Off duty',
  SB: 'Sleeper',
  D: 'Driving',
  ON: 'On duty',
}

export default function StopsTimeline({ trip }) {
  if (!trip?.days?.length) return null

  const events = []
  for (const day of trip.days) {
    for (const seg of day.segments) {
      if (seg.note === 'Before duty' || seg.note === 'After duty') continue
      events.push({
        ...seg,
        date: day.date,
      })
    }
  }

  // Collapse consecutive identical status+note
  const compact = []
  for (const ev of events) {
    const prev = compact[compact.length - 1]
    if (prev && prev.status === ev.status && prev.note === ev.note && prev.location === ev.location) {
      prev.end = ev.end
      continue
    }
    compact.push({ ...ev })
  }

  return (
    <section className="timeline-section">
      <h2>Duty timeline</h2>
      <p className="section-lede">Sequence of duty statuses across the trip.</p>
      <div className="timeline-strip" role="list">
        {compact.map((ev, i) => (
          <article key={i} className={`timeline-item status-${ev.status}`} role="listitem">
            <span className="tl-status">{statusLabel[ev.status] || ev.status}</span>
            <span className="tl-time">
              {new Date(ev.start).toLocaleString([], {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
              {' – '}
              {new Date(ev.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className="tl-place">{ev.note || ev.location}</span>
          </article>
        ))}
      </div>
    </section>
  )
}
