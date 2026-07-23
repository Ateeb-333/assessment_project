/**
 * Readable DOT daily log: HTML chrome for text, large SVG only for the duty grid.
 * Remarks & recap are real type — not microscopic newspaper print.
 */

const labelWidth = 128
const gridWidth = 960
const totalsWidth = 88
const rowHeight = 52
const gridHeight = 208
const pxPerHour = 40

const ROWS = { OFF: 0, SB: 1, D: 2, ON: 3 }
const ROW_LABELS = ['Off Duty', 'Sleeper Berth', 'Driving', 'On Duty (not driving)']
const STATUS_KEYS = ['OFF', 'SB', 'D', 'ON']

function minutesFromMidnight(iso) {
  const m = String(iso).match(/T(\d{2}):(\d{2})(?::(\d{2}))?/)
  if (m) {
    return Number(m[1]) * 60 + Number(m[2]) + Number(m[3] || 0) / 60
  }
  const d = new Date(iso)
  return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60
}

function xOf(iso) {
  return labelWidth + (minutesFromMidnight(iso) / 1440) * gridWidth
}

function yOf(status) {
  return ROWS[status] * rowHeight + rowHeight / 2
}

function buildPolyline(segments) {
  if (!segments?.length) return ''
  const pts = []
  segments.forEach((seg, i) => {
    const x1 = xOf(seg.start)
    const x2 = Math.max(x1, xOf(seg.end))
    const y = yOf(seg.status)
    if (i === 0) {
      pts.push(`${x1},${y}`)
    } else {
      const prev = segments[i - 1]
      const yPrev = yOf(prev.status)
      if (yPrev !== y) {
        pts.push(`${x1},${yPrev}`)
        pts.push(`${x1},${y}`)
      }
    }
    pts.push(`${x2},${y}`)
  })
  return pts.join(' ')
}

function parseDateParts(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number)
  return {
    month: String(m).padStart(2, '0'),
    day: String(d).padStart(2, '0'),
    year: String(y),
  }
}

function hourLabel(h) {
  if (h === 0 || h === 24) return 'Mid'
  if (h === 12) return 'Noon'
  return String(h)
}

function formatTime(iso) {
  const m = String(iso).match(/T(\d{2}):(\d{2})/)
  if (m) return `${m[1]}:${m[2]}`
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function LogSheet({ day, tripMeta }) {
  const { date, segments, totals, miles_driving = 0, remarks = [], recap } = day
  const poly = buildPolyline(segments)
  const totalSumRaw = Object.values(totals).reduce((a, b) => a + b, 0)
  // Float noise from hour splits can land at 23.99/24.01 — display snaps to 24.00.
  const totalSum = Math.abs(totalSumRaw - 24) < 0.02 ? 24 : totalSumRaw
  const parts = parseDateParts(date)
  const svgW = labelWidth + gridWidth + totalsWidth
  const svgH = gridHeight + 36

  const from = tripMeta?.from || '—'
  const to = tripMeta?.to || '—'
  const carrier = tripMeta?.carrier || 'Assessment Carrier LLC'
  const office = tripMeta?.office || 'Home Terminal, USA'
  const vehicle = tripMeta?.vehicle || 'Unit 101 / Trailer T-205'

  const remarkList = (
    remarks.length
      ? remarks
      : segments
          .filter((s) => s.note !== 'Before duty' && s.note !== 'After duty')
          .reduce((acc, seg) => {
            const prev = acc[acc.length - 1]
            if (!prev || prev.status !== seg.status) {
              acc.push({
                time: seg.start,
                location: seg.location || seg.note,
                status: seg.status,
                note: seg.note,
              })
            }
            return acc
          }, [])
  ).filter((r) => r.location)

  const onDutyToday =
    recap?.on_duty_today ?? day.on_duty_today ?? Number((totals.D + totals.ON).toFixed(2))

  return (
    <article className="log-sheet">
      <header className="log-chrome-header">
        <div className="log-chrome-titleblock">
          <p className="log-chrome-eyebrow">U.S. Department of Transportation</p>
          <h3>Drivers Daily Log — 24 hours</h3>
          <p className="log-chrome-copies">
            Original — file at home terminal · Duplicate — retain 8 days
          </p>
        </div>
        <div className="log-chrome-date" aria-label="Log date">
          <div>
            <strong>{parts.month}</strong>
            <span>Month</span>
          </div>
          <div>
            <strong>{parts.day}</strong>
            <span>Day</span>
          </div>
          <div>
            <strong>{parts.year}</strong>
            <span>Year</span>
          </div>
        </div>
      </header>

      <div className="log-chrome-meta">
        <div className="log-chrome-route">
          <p>
            <span>From</span> {from}
          </p>
          <p>
            <span>To</span> {to}
          </p>
        </div>
        <div className="log-chrome-miles">
          <div>
            <strong>{Number(miles_driving || 0).toFixed(0)}</strong>
            <span>Miles driving today</span>
          </div>
          <div>
            <strong>{Number(day.miles_today ?? miles_driving ?? 0).toFixed(0)}</strong>
            <span>Total mileage today</span>
          </div>
        </div>
        <div className="log-chrome-carrier">
          <p>
            <span>Carrier</span> {carrier}
          </p>
          <p>
            <span>Terminal</span> {office}
          </p>
          <p>
            <span>Vehicle</span> {vehicle}
          </p>
        </div>
      </div>

      <div className="log-grid-wrap">
        <svg
          className="log-svg"
          viewBox={`0 0 ${svgW} ${svgH}`}
          role="img"
          aria-label={`Duty status grid for ${date}`}
        >
          {Array.from({ length: 25 }, (_, h) => (
            <text
              key={`hl-${h}`}
              x={labelWidth + h * pxPerHour}
              y={18}
              textAnchor="middle"
              className="hour-label"
            >
              {hourLabel(h)}
            </text>
          ))}

          <g transform="translate(0, 28)">
            {ROW_LABELS.map((label, i) => (
              <g key={label}>
                <rect
                  x={0}
                  y={i * rowHeight}
                  width={svgW}
                  height={rowHeight}
                  fill={i % 2 === 0 ? '#ffffff' : '#f3f5f4'}
                />
                <text x={10} y={i * rowHeight + rowHeight / 2 + 5} className="row-label">
                  {label}
                </text>
                <text
                  x={labelWidth + gridWidth + totalsWidth / 2}
                  y={i * rowHeight + rowHeight / 2 + 5}
                  textAnchor="middle"
                  className="total-value"
                >
                  {(totals[STATUS_KEYS[i]] || 0).toFixed(2)}
                </text>
              </g>
            ))}

            {Array.from({ length: 25 }, (_, h) => (
              <line
                key={`v-${h}`}
                x1={labelWidth + h * pxPerHour}
                y1={0}
                x2={labelWidth + h * pxPerHour}
                y2={gridHeight}
                className="hour-line"
              />
            ))}
            {Array.from({ length: 24 * 4 }, (_, q) => {
              if (q % 4 === 0) return null
              const x = labelWidth + q * 10
              return ROW_LABELS.map((_, i) => (
                <line
                  key={`q-${q}-${i}`}
                  x1={x}
                  y1={i * rowHeight}
                  x2={x}
                  y2={i * rowHeight + 8}
                  className="quarter-tick"
                />
              ))
            })}
            {ROW_LABELS.map((_, i) => (
              <line
                key={`h-${i}`}
                x1={labelWidth}
                y1={i * rowHeight}
                x2={labelWidth + gridWidth}
                y2={i * rowHeight}
                className="row-rule"
              />
            ))}
            <line
              x1={labelWidth}
              y1={gridHeight}
              x2={labelWidth + gridWidth}
              y2={gridHeight}
              className="row-rule"
            />
            <line
              x1={labelWidth}
              y1={0}
              x2={labelWidth}
              y2={gridHeight}
              className="row-rule"
            />

            <rect
              x={labelWidth + gridWidth}
              y={0}
              width={totalsWidth}
              height={gridHeight}
              fill="none"
              className="totals-box"
            />
            <text
              x={labelWidth + gridWidth + totalsWidth / 2}
              y={-8}
              textAnchor="middle"
              className="totals-heading"
            >
              Total Hours
            </text>

            <polyline
              className="duty-line"
              points={poly}
              fill="none"
              stroke="#121a16"
              strokeWidth="3"
              strokeLinejoin="miter"
              strokeLinecap="square"
            />

            <text
              x={labelWidth + gridWidth + totalsWidth / 2}
              y={gridHeight + 22}
              textAnchor="middle"
              className="eq24"
            >
              = {totalSum.toFixed(2)}
            </text>
          </g>
        </svg>
      </div>

      <section className="log-remarks">
        <div className="log-block-head">
          <h4>Remarks</h4>
          <p>Place of each duty-status change (home terminal time)</p>
        </div>
        {remarkList.length === 0 ? (
          <p className="log-empty">No duty changes recorded.</p>
        ) : (
          <ol className="remark-list">
            {remarkList.map((r, i) => (
              <li key={`${r.time}-${i}`}>
                <time>{formatTime(r.time)}</time>
                <span className={`remark-status status-${r.status}`}>{r.status}</span>
                <strong>{r.location}</strong>
                {r.note && r.note !== r.location && <em>{r.note}</em>}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="log-recap">
        <div className="log-block-head">
          <h4>Recap — 70 hour / 8 day</h4>
          <p>Complete at end of day</p>
        </div>
        <div className="recap-grid">
          <div>
            <span>On duty today (D + ON)</span>
            <strong>{Number(onDutyToday).toFixed(2)} hrs</strong>
          </div>
          <div>
            <span>A. Last 8 days incl. today</span>
            <strong>{Number(recap?.a_hours_last_8_incl_today ?? 0).toFixed(2)} hrs</strong>
          </div>
          <div>
            <span>B. Available tomorrow (70 − A)</span>
            <strong>{Number(recap?.b_hours_available_tomorrow ?? 0).toFixed(2)} hrs</strong>
          </div>
          <div>
            <span>C. Last 8 days incl. today</span>
            <strong>{Number(recap?.c_hours_last_8_incl_today ?? 0).toFixed(2)} hrs</strong>
          </div>
        </div>
        <p className="recap-note">
          *If you took 34 consecutive hours off duty you have 70 hours available.
          {recap?.restart_taken_today ? ' — 34-hour restart recorded on this sheet.' : ''}
        </p>
      </section>
    </article>
  )
}
