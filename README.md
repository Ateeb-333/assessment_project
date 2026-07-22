# ELD Trip Planner

Full-stack trip planner that takes current / pickup / dropoff locations plus cycle hours used, then returns a **legal FMCSA Hours-of-Service schedule**, a **route map with stops**, and **DOT daily log sheets**.

## Live demo

- Frontend: _(add Vercel URL after deploy)_
- Backend API: _(add Render/Railway URL after deploy)_

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite on **Vercel** | Fast UI iteration; SVG log sheets render in the browser |
| Backend | Django + DRF on **Render / Railway** | Persistent process, Postgres, WhiteNoise — Vercel is a poor fit for a full Django app |
| Routing | OpenRouteService (`driving-hgv`, fallback `driving-car`) | HGV-aware when keyed; falls back to public OSRM + Nominatim without a key |
| Map tiles | OpenStreetMap via Leaflet | Free map API |

## Assumptions

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

## HOS rules implemented

Source: FMCSA *Interstate Truck Driver’s Guide to Hours of Service* (April 2022), property-carrying CMVs.

| Clock | Counts | Limit | Reset |
|---|---|---|---|
| **Driving** | Cumulative driving in a shift | 11 hrs | 10 consecutive hrs off duty (logged as SB) |
| **Window** | Elapsed wall time since going on duty | 14 hrs | 10 consecutive hrs off duty |
| **Break** | Driving since last ≥30 min non-driving | 8 hrs | Any 30 consecutive min not driving (OFF, ON, or SB) |
| **Cycle** | Total on-duty time (driving + non-driving) | 70 hrs / 8 days | 34 consecutive hrs off duty |

The 14-hour window does **not** pause for breaks, fuel, or loading. Pickup (1h ON) and fuel (30m ON) reset the break clock — the planner does not stack a redundant break after them. Non-driving work after the 14th hour is allowed by regulation; this planner inserts a 10-hour rest so the trip can continue legally.

Daily log sheets follow RODS requirements from the guide: date, total miles driving today, carrier/vehicle fields, 24-hour graph grid, remarks at each duty-status change, totals (=24), and a simplified 70/8 recap.

Reference PDF in repo: `fmcsa-hos-395-drivers-guide-to-hos-2022-04-28-0-1-.pdf`

## Known limitations

- No authentication or user accounts
- No trip history UI
- No split sleeper berth provision
- No 8-day rolling cycle roll-off (see assumption #3)
- No adverse driving conditions exception
- No PDF export
- No multi-timezone handling

## Local setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional ORS_API_KEY
python manage.py migrate
python manage.py runserver
```

API: `http://127.0.0.1:8000/api/trips/` · health: `/api/health/`

### Frontend

```bash
cd frontend
npm install
# optional: echo 'VITE_API_URL=http://127.0.0.1:8000' > .env
npm run dev
```

App: `http://127.0.0.1:5173`

### Environment variables

**Backend**

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS` (your Vercel origin)
- `ORS_API_KEY` (optional)
- `DATABASE_URL` (Postgres in production; SQLite locally)

**Frontend**

- `VITE_API_URL` — backend origin, e.g. `https://your-api.onrender.com`

## Running the tests

```bash
cd backend
source .venv/bin/activate
python manage.py test trips
```

Covers short trips, 8h break + 11h rest, fuel stops, 34h restart, midnight splits, and the 24.00 totals invariant.

## API

`POST /api/trips/`

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Des Moines, IA",
  "dropoff_location": "Denver, CO",
  "current_cycle_used": 12.5,
  "start_datetime": "2026-07-23T06:00:00"
}
```

Response includes `route`, `stops`, `days` (segments + totals), and `summary`.

## Project layout

```
backend/          Django + DRF, pure-Python HOS engine
frontend/         React + Vite, Leaflet map, SVG log sheets
eld-trip-planner-build-plan.md
```
