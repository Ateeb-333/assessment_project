# ELD Trip Planner — Build Plan

**Assessment:** Full Stack Developer (Django + React)
**Budget:** 24 hours
**Deliverables:** GitHub repo · live hosted URL · 3–5 min Loom

---

## 1. What is actually being asked

Build a web app that takes four trip inputs, computes a **legal** driving schedule under FMCSA Hours-of-Service rules, and presents the result two ways: a **map** with stops, and **filled-in DOT daily log sheets** drawn on the standard grid.

**Inputs**

| Field | Type | Notes |
|---|---|---|
| Current location | string | Geocoded |
| Pickup location | string | Geocoded |
| Dropoff location | string | Geocoded |
| Current cycle used | float (hrs) | On-duty hours already burned in the 70hr/8day cycle |

**Outputs**

1. Map showing the route, with rest stops, fuel stops, and pickup/dropoff marked. Free map API required.
2. Daily log sheets — drawn on the grid, one per calendar day, multiple sheets for multi-day trips.

**Given assumptions (from the brief)**

- Property-carrying driver, 70 hrs / 8 days, no adverse driving conditions
- Fueling at least once every 1,000 miles
- 1 hour each for pickup and drop-off

**Grading signals stated in the brief**

- Hosted version will be tested for accuracy
- UI/UX is explicitly weighted and "can compensate for some inaccuracies in output"

> **Read this as:** a beautiful, faithful log sheet beats a marginally more correct one that looks like a spreadsheet.

---

## 2. Hours-of-Service rules to encode

Four constraints run simultaneously. Source: FMCSA *Interstate Truck Driver's Guide to Hours of Service*, April 2022.

| Clock | Counts | Limit | Reset |
|---|---|---|---|
| **Driving** | Cumulative driving in a shift | 11 hrs | 10 consecutive hrs off duty |
| **Window** | **Elapsed wall time** since going on duty | 14 hrs | 10 consecutive hrs off duty |
| **Break** | Driving since last ≥30 min non-driving | 8 hrs | Any 30 consecutive min not driving |
| **Cycle** | Total on-duty time (driving + non-driving) | 70 hrs / 8 days | 34 consecutive hrs off duty |

### The two subtleties that break naive implementations

**1. The 14-hour window does not pause.**
It is elapsed clock time from first going on duty. Breaks, fuel stops, and loading time all consume it. A driver can have 4 driving hours left on the 11-hr clock and still be legally grounded because 14 hours of wall time have passed.
→ *Store window start as a timestamp, not an accumulator.*

**2. Mandatory stops satisfy the 30-minute break.**
The 1-hour pickup is on-duty-not-driving. A 30-minute fuel stop is on-duty-not-driving. Both are ≥30 consecutive minutes of not driving, so both reset the break counter.
→ *Don't stack a redundant break immediately after a pickup or fuel stop.*

### Duty status codes

| Code | Label | Counts toward |
|---|---|---|
| `OFF` | Off Duty | nothing |
| `SB` | Sleeper Berth | nothing |
| `D` | Driving | Driving, Window, Break, Cycle |
| `ON` | On Duty (Not Driving) | Window, Cycle |

---

## 3. Assumptions register

The brief is underdetermined in several places. Decide each one, **and put this table in your README** — documenting assumptions is itself a seniority signal.

| # | Ambiguity | Decision |
|---|---|---|
| 1 | Trip start time not an input | Optional `start_datetime` field, defaults to now |
| 2 | Driver's shift state at trip start unknown | Assume driver just completed 10 hrs off — 11 and 14 clocks fresh |
| 3 | 70/8 is a *rolling* window but input is a scalar | Cannot model day-by-day roll-off. Cycle only increases; recovers only via 34-hr restart |
| 4 | Fuel stop duration unspecified | 30 min, on duty (not driving) |
| 5 | Cycle exhausted mid-trip | Insert 34-hour restart, log those days |
| 6 | Sleeper berth vs off duty for 10-hr rest | Log as Sleeper Berth. No split-sleeper provision |
| 7 | Pre/post-trip inspections | Folded into the 1-hr pickup/dropoff |
| 8 | Time zone | Single time zone throughout; logs use it as "home terminal time" |
| 9 | Route shape | Two legs: current → pickup → dropoff, one continuous clock state across both |
| 10 | Log sheet boundaries | One sheet per calendar day, midnight to midnight; segments split at midnight |

---

## 4. Architecture

```
React (Vite) ──── Vercel
     │  POST /api/trips/
     ▼
Django + DRF ──── Render / Railway / Fly.io
     │
     ├── OpenRouteService  (geocode + driving-hgv route)
     └── PostgreSQL        (one Trip model)
```

**Do not deploy Django on Vercel.** The brief says "can use Vercel.app," but Vercel is built for frontend and serverless functions — no persistent processes, awkward static files, cold starts. Deploy React on Vercel and Django on Render or Railway. Nothing in the brief forbids this and it is the choice a competent developer makes. Note the reasoning in your README.

**Render the log sheets as SVG in React**, not server-side. The backend returns structured duty segments; the frontend draws them. Faster to iterate, scales cleanly, prints well, and it's where your UI marks come from.

**Keep one Django model.** A `Trip` storing inputs plus the computed result JSON. Without it you have a calculator in a Django-shaped trench coat, and the reviewer will notice.

---

## 5. The HOS engine

This is the heart of the assessment. Write it as **pure Python with no Django imports** so you can unit test it in isolation.

### Input

A queue of work items derived from the route:

```
[ drive(leg_A), on_duty(1.0, "Pickup"), drive(leg_B), on_duty(1.0, "Dropoff") ]
```

### State

```python
@dataclass
class ClockState:
    now: datetime
    driving_this_shift: float   # → 11
    window_start: datetime      # now - window_start → 14
    driving_since_break: float  # → 8
    cycle_used: float           # → 70
    miles_since_fuel: float     # → 1000
```

### Core loop

For each driving item, repeatedly compute the **binding constraint**:

```python
max_drive = min(
    11.0 - driving_this_shift,
    14.0 - hours_since(window_start),
    8.0  - driving_since_break,
    remaining_leg_hours,
    hours_until_next_fuel_point,
)
```

Advance by `max_drive`, emit a `D` segment, then insert the stop that the binding constraint demands:

| Binding constraint | Insert |
|---|---|
| 11-hr driving | 10-hr `SB` rest → reset driving, window, break |
| 14-hr window | 10-hr `SB` rest → reset driving, window, break |
| 8-hr break | 30-min `OFF` break → reset break only |
| Fuel point | 30-min `ON` fuel stop → resets break as a side effect |
| Leg complete | Move to next work item |

Before **any** driving, check the cycle:

```python
if cycle_used >= 70.0:
    emit 34-hour OFF segment
    cycle_used = 0.0
    reset driving, window, break
```

### Output

A flat list of segments:

```python
{
  "start": "2026-07-23T06:00:00",
  "end":   "2026-07-23T07:00:00",
  "status": "ON",
  "location": "Chicago, IL",
  "note": "Pickup"
}
```

A second, separate function splits this list at midnight boundaries into per-day sheets and computes the four row totals (which must sum to exactly 24.00 per sheet — assert this).

### Stop placement on the map

Stops need coordinates, not just times.

- **Rest and break stops:** interpolate along the route polyline by **cumulative drive time**
- **Fuel stops:** interpolate by **cumulative distance** (every 1,000 mi)
- Reverse-geocode the resulting point to get "City, ST" for the Remarks line

Precompute a cumulative distance/time array over the polyline once, then binary-search it. Cache reverse-geocode results aggressively.

---

## 6. API contract

**`POST /api/trips/`**

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Des Moines, IA",
  "dropoff_location": "Denver, CO",
  "current_cycle_used": 12.5,
  "start_datetime": "2026-07-23T06:00:00"
}
```

**Response**

```json
{
  "id": 1,
  "route": {
    "geometry": [[41.87, -87.62], "..."],
    "total_distance_miles": 1085.4,
    "total_drive_hours": 17.2
  },
  "stops": [
    {
      "type": "pickup",
      "lat": 41.59, "lng": -93.62,
      "label": "Des Moines, IA",
      "arrival": "2026-07-23T12:30:00",
      "duration_hours": 1.0
    }
  ],
  "days": [
    {
      "date": "2026-07-23",
      "segments": ["..."],
      "totals": { "OFF": 6.5, "SB": 0.0, "D": 11.0, "ON": 6.5 }
    }
  ],
  "summary": {
    "cycle_used_start": 12.5,
    "cycle_used_end": 45.0,
    "restarts_taken": 0,
    "total_days": 3
  }
}
```

`stop.type` ∈ `pickup | dropoff | fuel | break | rest | restart`

---

## 7. SVG log grid geometry

The grid math is fiddlier than it looks. Get it right once, in constants.

```
labelWidth   = 80        // "Off Duty", "Sleeper Berth", ...
gridWidth    = 960       // 24 hrs × 40 px
totalsWidth  = 60
rowHeight    = 40
gridHeight   = 160       // 4 rows

pxPerHour    = 40
pxPerQuarter = 10        // tick marks every 15 min
```

**Time to x-coordinate:**

```js
const x = (date) => labelWidth + (minutesFromMidnight(date) / 1440) * gridWidth;
```

**Row centre y-coordinate:**

```js
const ROWS = { OFF: 0, SB: 1, D: 2, ON: 3 };
const y = (status) => ROWS[status] * rowHeight + rowHeight / 2;
```

**Drawing a day's segments** — build one continuous polyline:

1. For each segment, a horizontal line from `x(start)` to `x(end)` at `y(status)`
2. Between consecutive segments, a vertical connector at the boundary `x` from `y(prev)` to `y(next)`
3. Emit as a single `<polyline>` with `fill="none"`, rounded joins

**Grid chrome:**

- Vertical hour lines full height, quarter-hour ticks short (from row top, ~6 px)
- Hour labels above the grid: `Midnight, 2, 3, ... Noon, 13, ... 23`
- Row labels left, totals right, `=24` beneath the totals column
- Remarks: rotated text (`transform="rotate(-60)"`) below the grid at each duty-change `x`, showing "City, ST"

Match the visual language of the blank DOT form — dark row separators, thin tick marks, the totals column boxed on the right. Faithfulness here is what the reviewer sees first.

---

## 8. Hour-by-hour schedule

| Hours | Work | Done when |
|---|---|---|
| 0–1 | Repo, Django+DRF skeleton, Vite+React skeleton, **deploy both as empty shells** | Hello-world visible at both public URLs |
| 1–3 | Geocoding + routing integration | Given two city strings, you print a polyline, distance, and duration |
| 3–9 | **HOS engine**, pure Python, unit tested | All five test cases in §10 pass |
| 9–12 | SVG log sheet renderer | Hardcoded segments render as a convincing DOT form |
| 12–16 | React UI: form, Leaflet map, stops timeline, log sheets | Full flow works locally |
| 16–19 | Design polish | See §11 |
| 19–21 | Redeploy, fix CORS / env vars / build config | Full flow works on the public URL |
| 21–23 | README + Loom recording | Both links ready |
| 23–24 | Buffer | You will need it |

**Deployment happens in hour one, not hour twenty.** These assessments are not usually lost on the algorithm; they are lost on discovering at hour 22 that the build config is wrong.

---

## 9. Risks to defuse before hour three

| Risk | Mitigation |
|---|---|
| Routing API rejects long routes | OpenRouteService free tier caps route distance and daily requests, and `driving-hgv` is stricter than `driving-car`. **Verify the actual limits now**, and build a fallback to `driving-car` if hgv rejects the route. Test with a genuinely long trip (e.g. Chicago → Los Angeles) on day one |
| Geocoder rate limits | Nominatim's public instance throttles hard. Cache every lookup. Consider ORS Pelias instead |
| CORS failures | Set `CORS_ALLOWED_ORIGINS` to your Vercel domain on day one |
| Static files on Django host | Use WhiteNoise; configure before first deploy |
| Secrets in repo | `.env` from the start; never commit the API key |
| Floating-point totals ≠ 24.00 | Work in integer minutes internally, convert to hours only at the boundary |

---

## 10. Test cases

Write these **before** the UI. If they pass, the rest is presentation.

| # | Scenario | Expects |
|---|---|---|
| 1 | Short trip, 4 hrs driving, cycle used 10 | One log sheet, no rest, break not triggered |
| 2 | 13 hrs driving, cycle used 10 | 30-min break inserted at 8 hrs; 11-hr limit forces a 10-hr rest; two log sheets |
| 3 | 1,400 mi trip | At least one fuel stop; fuel stop resets the break counter (no redundant break after it) |
| 4 | Cycle used = 68, trip needs 20 on-duty hrs | 34-hr restart appears; cycle resets to 0; log sheets cover the restart days |
| 5 | Trip crossing midnight mid-drive | Driving segment split cleanly at 00:00; both sheets total exactly 24.00 |

Plus an invariant test: **every generated sheet's four totals sum to 24.00.**

---

## 11. UI/UX — where the marks are

The brief says design can compensate for output inaccuracy. Budget the three hours.

- **Pick a real typeface.** Not system default. Something with character for headings, something neutral and legible for data.
- **One accent colour**, used deliberately — for the route line, active stops, and primary action. Everything else neutral.
- **Layout:** inputs collapse to a compact summary bar after submit; map takes the visual lead; log sheets stack below with clear day headers.
- **Stops timeline** between map and logs: a horizontal strip showing the sequence of duty states with times and locations. Cheap to build, reads as thoughtful.
- **Loading state** that isn't a spinner — routing plus geocoding takes several seconds.
- **Empty and error states.** "Could not find that location" beats a stack trace.
- **Print stylesheet** for the log sheets if you have spare time. Very high perceived effort, very low actual effort.

---

## 12. Scope cuts — decided in advance

Cut these without guilt, and list them in the README as known limitations:

- No authentication or user accounts
- No trip history UI
- No split sleeper berth provision
- No 8-day rolling cycle roll-off (see assumption #3)
- No adverse driving conditions exception
- No PDF export unless you finish early
- No multi-timezone handling

---

## 13. README outline

1. What it does — two sentences and a screenshot
2. Live demo link
3. Stack and why (including the Vercel/Render split reasoning)
4. **Assumptions table from §3** — verbatim
5. HOS rules implemented, with the four clocks table
6. Known limitations (§12)
7. Local setup: backend, frontend, env vars
8. Running the tests

---

## 14. Loom script (3–5 min)

| Time | Content |
|---|---|
| 0:00–0:30 | What the app does, one sentence. Show the finished output immediately |
| 0:30–1:30 | Live demo: enter a multi-day trip, walk the map, walk the log sheets |
| 1:30–3:00 | The HOS engine — show the binding-constraint loop, explain the 14-hr window subtlety |
| 3:00–4:00 | The SVG log renderer — show the grid geometry |
| 4:00–4:30 | Assumptions you made and why; known limitations |

Lead with the working product, not the code. Reviewers decide in the first thirty seconds.

---

## 15. Definition of done

- [ ] Public URL loads and completes a full trip end to end
- [ ] Multi-day trip produces multiple correct log sheets
- [ ] Every sheet's totals sum to 24.00
- [ ] Map shows route plus all stop types with labels
- [ ] Cycle-exhaustion input produces a 34-hr restart without crashing
- [ ] Invalid location input shows a friendly error
- [ ] README contains the assumptions table
- [ ] Repo is public, no secrets committed
- [ ] Loom recorded, under 5 minutes
