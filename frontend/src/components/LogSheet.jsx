const labelWidth = 110
const gridWidth = 960
const totalsWidth = 64
const rowHeight = 40
const gridHeight = 160
const pxPerHour = 40

const ROWS = { OFF: 0, SB: 1, D: 2, ON: 3 }
const ROW_LABELS = ['Off Duty', 'Sleeper Berth', 'Driving', 'On Duty (not driving)']

function minutesFromMidnight(iso) {
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
    const x2 = xOf(seg.end)
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

function remarkPoints(segments) {
  const remarks = []
  let lastStatus = null
  for (const seg of segments) {
    if (seg.note === 'Before duty' || seg.note === 'After duty') continue
    if (seg.status !== lastStatus) {
      const label = seg.location || seg.note
      if (label) {
        remarks.push({ x: xOf(seg.start), text: label })
      }
      lastStatus = seg.status
    }
  }
  return remarks
}

export default function LogSheet({ day, tripMeta }) {
  const { date, segments, totals } = day
  const poly = buildPolyline(segments)
  const remarks = remarkPoints(segments)
  const totalSum = Object.values(totals).reduce((a, b) => a + b, 0)
  const svgW = labelWidth + gridWidth + totalsWidth
  const svgH = 48 + gridHeight + 90

  const d = new Date(date + 'T12:00:00')
  const dateLabel = d.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <article className="log-sheet">
      <header className="log-sheet-header">
        <div>
          <h3>Drivers Daily Log (24 hours)</h3>
          <p>
            From: {tripMeta?.from || '—'} &nbsp;·&nbsp; To: {tripMeta?.to || '—'}
          </p>
        </div>
        <div className="log-date">{dateLabel}</div>
      </header>

      <svg
        className="log-svg"
        viewBox={`0 0 ${svgW} ${svgH}`}
        role="img"
        aria-label={`Duty log for ${dateLabel}`}
      >
        {/* Hour labels */}
        {Array.from({ length: 25 }, (_, h) => {
          const x = labelWidth + h * pxPerHour
          let label = ''
          if (h === 0 || h === 24) label = 'Midnight'
          else if (h === 12) label = 'Noon'
          else if (h < 12) label = String(h)
          else label = String(h)
          return (
            <text
              key={`hl-${h}`}
              x={x}
              y={28}
              textAnchor="middle"
              className="hour-label"
            >
              {label}
            </text>
          )
        })}

        <g transform="translate(0, 36)">
          {/* Row backgrounds */}
          {ROW_LABELS.map((label, i) => (
            <g key={label}>
              <rect
                x={0}
                y={i * rowHeight}
                width={svgW}
                height={rowHeight}
                className={i % 2 === 0 ? 'row-even' : 'row-odd'}
              />
              <text
                x={8}
                y={i * rowHeight + rowHeight / 2 + 4}
                className="row-label"
              >
                {label}
              </text>
              <text
                x={labelWidth + gridWidth + totalsWidth / 2}
                y={i * rowHeight + rowHeight / 2 + 4}
                textAnchor="middle"
                className="total-value"
              >
                {(totals[['OFF', 'SB', 'D', 'ON'][i]] || 0).toFixed(2)}
              </text>
            </g>
          ))}

          {/* Grid lines */}
          {Array.from({ length: 25 }, (_, h) => {
            const x = labelWidth + h * pxPerHour
            return (
              <line
                key={`v-${h}`}
                x1={x}
                y1={0}
                x2={x}
                y2={gridHeight}
                className="hour-line"
              />
            )
          })}
          {Array.from({ length: 24 * 4 }, (_, q) => {
            if (q % 4 === 0) return null
            const x = labelWidth + q * 10
            return ROW_LABELS.map((_, i) => (
              <line
                key={`q-${q}-${i}`}
                x1={x}
                y1={i * rowHeight}
                x2={x}
                y2={i * rowHeight + 6}
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

          {/* Totals box */}
          <rect
            x={labelWidth + gridWidth}
            y={0}
            width={totalsWidth}
            height={gridHeight}
            className="totals-box"
            fill="none"
          />
          <text
            x={labelWidth + gridWidth + totalsWidth / 2}
            y={-8}
            textAnchor="middle"
            className="totals-heading"
          >
            Total Hours
          </text>

          {/* Duty polyline */}
          <polyline
            points={poly}
            fill="none"
            stroke="#0f172a"
            strokeWidth="2.25"
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {/* =24 */}
          <text
            x={labelWidth + gridWidth + totalsWidth / 2}
            y={gridHeight + 18}
            textAnchor="middle"
            className="eq24"
          >
            = {totalSum.toFixed(2)}
          </text>
        </g>

        {/* Remarks */}
        <g transform="translate(0, 36)">
          {remarks.map((r, i) => (
            <text
              key={i}
              x={r.x}
              y={gridHeight + 28}
              className="remark"
              transform={`rotate(-60 ${r.x} ${gridHeight + 28})`}
            >
              {r.text.length > 28 ? `${r.text.slice(0, 26)}…` : r.text}
            </text>
          ))}
        </g>
      </svg>

      <p className="remarks-caption">
        Remarks show where each change of duty occurred (home terminal time).
      </p>
    </article>
  )
}
