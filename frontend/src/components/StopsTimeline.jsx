const statusLabel = {
  OFF: 'Off duty',
  SB: 'Sleeper',
  D: 'Driving',
  ON: 'On duty',
}

function formatRange(start, end) {
  const s = new Date(start)
  const e = new Date(end)
  const sameDay = s.toDateString() === e.toDateString()
  const startStr = s.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const endStr = sameDay
    ? e.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : e.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
  return `${startStr} – ${endStr}`
}

export default function StopsTimeline({ trip }) {
  if (!trip?.days?.length) return null

  const events = []
  for (const day of trip.days) {
    for (const seg of day.segments) {
      if (seg.note === 'Before duty' || seg.note === 'After duty') continue
      events.push({ ...seg, date: day.date })
    }
  }

  const compact = []
  for (const ev of events) {
    const prev = compact[compact.length - 1]
    if (
      prev &&
      prev.status === ev.status &&
      prev.note === ev.note &&
      prev.location === ev.location
    ) {
      prev.end = ev.end
      continue
    }
    compact.push({ ...ev })
  }

  return (
    <section className="timeline-section reveal" style={{ '--delay': '0.12s' }}>
      <h2>Duty timeline</h2>
      <p className="section-lede">Status changes across the full trip clock.</p>
      <div className="timeline-strip" role="list">
        {compact.map((ev, i) => (
          <article
            key={i}
            className={`timeline-item status-${ev.status}`}
            role="listitem"
            style={{ '--i': i }}
          >
            <span className="tl-status">{statusLabel[ev.status] || ev.status}</span>
            <span className="tl-place">{ev.note || ev.location}</span>
            <span className="tl-time">{formatRange(ev.start, ev.end)}</span>
            {ev.location && ev.note && ev.note !== ev.location && (
              <span className="tl-loc">{ev.location}</span>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
