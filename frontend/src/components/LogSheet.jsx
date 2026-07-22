/**
 * DOT Drivers Daily Log — visual language matched to the FMCSA blank form
 * and RODS requirements in the Interstate Truck Driver's Guide (Apr 2022):
 * date, miles driving today, carrier/vehicle fields, 24h graph grid,
 * remarks at duty changes, total hours (=24), and 70/8 recap.
 */

const labelWidth = 100
const gridWidth = 960
const totalsWidth = 70
const rowHeight = 36
const gridHeight = 144
const pxPerHour = 40
const headerH = 118
const remarksH = 78
const recapH = 72
const pad = 12

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
  return { month: String(m).padStart(2, '0'), day: String(d).padStart(2, '0'), year: String(y) }
}

function hourLabel(h) {
  if (h === 0 || h === 24) return 'Midnight'
  if (h === 12) return 'Noon'
  return String(h)
}

export default function LogSheet({ day, tripMeta }) {
  const { date, segments, totals, miles_driving = 0, remarks = [], recap } = day
  const poly = buildPolyline(segments)
  const totalSum = Object.values(totals).reduce((a, b) => a + b, 0)
  const parts = parseDateParts(date)
  const svgW = pad * 2 + labelWidth + gridWidth + totalsWidth
  const gridTop = headerH
  const remarksTop = gridTop + gridHeight + 28
  const recapTop = remarksTop + remarksH + 8
  const svgH = recapTop + recapH + pad

  const from = tripMeta?.from || '—'
  const to = tripMeta?.to || '—'
  const carrier = tripMeta?.carrier || 'Assessment Carrier LLC'
  const office = tripMeta?.office || 'Home Terminal, USA'
  const vehicle = tripMeta?.vehicle || 'Unit 101 / Trailer T-205'

  const remarkPoints = (remarks.length
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
            })
          }
          return acc
        }, [])
  ).filter((r) => r.location)

  return (
    <article className="log-sheet">
      <svg
        className="log-svg"
        viewBox={`0 0 ${svgW} ${svgH}`}
        role="img"
        aria-label={`Drivers daily log for ${date}`}
      >
        {/* Outer border */}
        <rect
          x={1}
          y={1}
          width={svgW - 2}
          height={svgH - 2}
          fill="#fff"
          stroke="#111"
          strokeWidth="1.5"
        />

        {/* ===== HEADER ===== */}
        <text x={pad + 4} y={22} className="log-title">
          Drivers Daily Log (24 hours)
        </text>
        <text x={svgW - pad - 4} y={16} textAnchor="end" className="log-tiny">
          Original — File at home terminal
        </text>
        <text x={svgW - pad - 4} y={28} textAnchor="end" className="log-tiny">
          Duplicate — Driver retains for 8 days
        </text>

        {/* Date boxes */}
        <g transform={`translate(${svgW / 2 - 70}, 8)`}>
          {[
            { label: '(month)', val: parts.month, x: 0 },
            { label: '(day)', val: parts.day, x: 48 },
            { label: '(year)', val: parts.year, x: 96 },
          ].map((box) => (
            <g key={box.label} transform={`translate(${box.x}, 0)`}>
              <rect x={0} y={0} width={42} height={22} fill="none" stroke="#111" />
              <text x={21} y={15} textAnchor="middle" className="log-date-val">
                {box.val}
              </text>
              <text x={21} y={34} textAnchor="middle" className="log-tiny">
                {box.label}
              </text>
            </g>
          ))}
        </g>

        {/* From / To */}
        <text x={pad + 4} y={52} className="log-field-label">
          From: <tspan className="log-field-value">{from}</tspan>
        </text>
        <text x={pad + 4} y={68} className="log-field-label">
          To: <tspan className="log-field-value">{to}</tspan>
        </text>

        {/* Miles boxes */}
        <g transform={`translate(${pad + 4}, 78)`}>
          <rect x={0} y={0} width={88} height={32} fill="none" stroke="#111" />
          <text x={44} y={14} textAnchor="middle" className="log-miles-val">
            {Number(miles_driving || 0).toFixed(0)}
          </text>
          <text x={44} y={28} textAnchor="middle" className="log-tiny">
            Total Miles Driving Today
          </text>

          <rect x={96} y={0} width={88} height={32} fill="none" stroke="#111" />
          <text x={140} y={14} textAnchor="middle" className="log-miles-val">
            {Number(day.miles_today ?? miles_driving ?? 0).toFixed(0)}
          </text>
          <text x={140} y={28} textAnchor="middle" className="log-tiny">
            Total Mileage Today
          </text>

          <rect x={192} y={0} width={220} height={32} fill="none" stroke="#111" />
          <text x={200} y={14} className="log-field-value">
            {vehicle}
          </text>
          <text x={200} y={28} className="log-tiny">
            Truck/Tractor and Trailer Numbers
          </text>
        </g>

        {/* Carrier lines */}
        <g transform={`translate(${svgW - pad - 320}, 52)`}>
          <line x1={0} y1={14} x2={310} y2={14} stroke="#111" strokeWidth="0.75" />
          <text x={0} y={12} className="log-field-value">
            {carrier}
          </text>
          <text x={0} y={26} className="log-tiny">
            Name of Carrier or Carriers
          </text>
          <line x1={0} y1={44} x2={310} y2={44} stroke="#111" strokeWidth="0.75" />
          <text x={0} y={42} className="log-field-value">
            {office}
          </text>
          <text x={0} y={56} className="log-tiny">
            Main Office / Home Terminal Address
          </text>
        </g>

        {/* ===== GRID ===== */}
        <g transform={`translate(${pad}, ${gridTop})`}>
          {/* Hour labels */}
          {Array.from({ length: 25 }, (_, h) => (
            <text
              key={`hl-${h}`}
              x={labelWidth + h * pxPerHour}
              y={-6}
              textAnchor="middle"
              className="hour-label"
            >
              {hourLabel(h)}
            </text>
          ))}

          {ROW_LABELS.map((label, i) => (
            <g key={label}>
              <rect
                x={0}
                y={i * rowHeight}
                width={labelWidth + gridWidth + totalsWidth}
                height={rowHeight}
                fill={i % 2 === 0 ? '#fff' : '#f5f5f5'}
                stroke="none"
              />
              <text x={6} y={i * rowHeight + rowHeight / 2 + 4} className="row-label">
                {label}
              </text>
              <text
                x={labelWidth + gridWidth + totalsWidth / 2}
                y={i * rowHeight + rowHeight / 2 + 4}
                textAnchor="middle"
                className="total-value"
              >
                {(totals[STATUS_KEYS[i]] || 0).toFixed(2)}
              </text>
            </g>
          ))}

          {/* Hour lines + quarter ticks */}
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
                y2={i * rowHeight + 5}
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
          <line x1={labelWidth} y1={0} x2={labelWidth} y2={gridHeight} className="row-rule" />

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
            points={poly}
            fill="none"
            stroke="#0a0a0a"
            strokeWidth="2.4"
            strokeLinejoin="miter"
            strokeLinecap="square"
          />

          <text
            x={labelWidth + gridWidth + totalsWidth / 2}
            y={gridHeight + 16}
            textAnchor="middle"
            className="eq24"
          >
            ={totalSum.toFixed(2)}
          </text>
        </g>

        {/* ===== REMARKS ===== */}
        <g transform={`translate(${pad}, ${remarksTop})`}>
          <text x={0} y={0} className="section-head">
            Remarks
          </text>
          <rect
            x={0}
            y={6}
            width={labelWidth + gridWidth + totalsWidth}
            height={remarksH - 10}
            fill="none"
            stroke="#111"
            strokeWidth="0.9"
          />
          {remarkPoints.map((r, i) => {
            const x = Math.min(
              Math.max(xOf(r.time), 8),
              labelWidth + gridWidth - 8
            )
            const text = r.location.length > 22 ? `${r.location.slice(0, 20)}…` : r.location
            return (
              <text
                key={`${r.time}-${i}`}
                x={x}
                y={remarksH - 18}
                className="remark"
                transform={`rotate(-55 ${x} ${remarksH - 18})`}
              >
                {text}
              </text>
            )
          })}
          <text x={6} y={remarksH - 2} className="log-tiny">
            Enter place reported / released and where each change of duty occurred (home terminal
            time).
          </text>
          <text x={labelWidth + gridWidth - 4} y={22} textAnchor="end" className="log-tiny">
            Shipper &amp; Commodity / DVL —
          </text>
        </g>

        {/* ===== RECAP (70/8) ===== */}
        <g transform={`translate(${pad}, ${recapTop})`}>
          <text x={0} y={0} className="section-head">
            Recap: Complete at end of day
          </text>
          <text x={0} y={18} className="log-field-label">
            On duty hours today (lines 3 &amp; 4):{' '}
            <tspan className="log-field-value">
              {(recap?.on_duty_today ?? day.on_duty_today ?? totals.D + totals.ON).toFixed(2)}
            </tspan>
          </text>

          <g transform="translate(0, 28)">
            <text x={0} y={0} className="section-head">
              70 Hour / 8 Day Drivers
            </text>
            <text x={0} y={16} className="log-tiny">
              A. Total on duty last 8 days incl. today:{' '}
              <tspan className="log-field-value">
                {(recap?.a_hours_last_8_incl_today ?? 0).toFixed(2)}
              </tspan>
            </text>
            <text x={280} y={16} className="log-tiny">
              B. Available tomorrow (70 − A):{' '}
              <tspan className="log-field-value">
                {(recap?.b_hours_available_tomorrow ?? 0).toFixed(2)}
              </tspan>
            </text>
            <text x={520} y={16} className="log-tiny">
              C. On duty last 8 days incl. today:{' '}
              <tspan className="log-field-value">
                {(recap?.c_hours_last_8_incl_today ?? 0).toFixed(2)}
              </tspan>
            </text>
          </g>
          <text x={0} y={62} className="log-tiny italic">
            *If you took 34 consecutive hours off duty you have 70 hours available.
            {recap?.restart_taken_today ? ' — 34-hour restart recorded on this sheet.' : ''}
          </text>
        </g>
      </svg>
    </article>
  )
}
