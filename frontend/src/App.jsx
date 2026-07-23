import { useState } from 'react'
import { createTrip } from './api'
import TripForm from './components/TripForm'
import TripSummary from './components/TripSummary'
import RouteMap from './components/RouteMap'
import StopsTimeline from './components/StopsTimeline'
import LogSheet from './components/LogSheet'
import LoadingState from './components/LoadingState'
import './App.css'

export default function App() {
  const [trip, setTrip] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(payload) {
    setLoading(true)
    setError('')
    try {
      const data = await createTrip(payload)
      setTrip(data)
    } catch (err) {
      setTrip(null)
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setTrip(null)
    setError('')
  }

  return (
    <div className={`app ${trip ? 'app-results' : 'app-home'}`}>
      <div className="atmosphere" aria-hidden="true">
        <div className="atmosphere-grid" />
        <div className="atmosphere-glow" />
      </div>

      <header className="site-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ELD
          </span>
          <div className="brand-text">
            <p className="brand-kicker">Hours-of-Service</p>
            <h1>Trip Planner</h1>
          </div>
        </div>
        {trip && !loading && (
          <button type="button" className="btn-ghost header-reset" onClick={reset}>
            Plan another trip
          </button>
        )}
      </header>

      <main>
        {!trip && !loading && (
          <section className="hero-panel">
            <div className="hero-copy">
              <h2>
                <span className="hero-brand">ELD</span> schedules
                <br />
                you can log.
              </h2>
              <p>
                Enter current, pickup, and dropoff. We build a legal FMCSA
                schedule, map the stops, and fill DOT daily log sheets.
              </p>
            </div>
            <TripForm onSubmit={handleSubmit} loading={loading} />
          </section>
        )}

        {loading && <LoadingState />}

        {error && !loading && (
          <div className="error-banner" role="alert">
            <div>
              <strong>Could not plan trip</strong>
              <p>{error}</p>
            </div>
            <button type="button" className="btn-ghost" onClick={() => setError('')}>
              Dismiss
            </button>
          </div>
        )}

        {trip && !loading && (
          <div className="results">
            <TripSummary trip={trip} onReset={reset} />

            <section className="map-section reveal" style={{ '--delay': '0.05s' }}>
              <div className="section-head-row">
                <div>
                  <h2>Route &amp; stops</h2>
                  <p className="section-lede">
                    Pickup, dropoff, fuel, rest, and break markers on the drive.
                  </p>
                </div>
              </div>
              <RouteMap trip={trip} />
            </section>

            <StopsTimeline trip={trip} />

            <section className="logs-section reveal" style={{ '--delay': '0.18s' }}>
              <div className="section-head-row">
                <div>
                  <h2>Daily log sheets</h2>
                  <p className="section-lede">
                    FMCSA Drivers Daily Log — grid, remarks, miles, and 70/8 recap.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => window.print()}
                >
                  Print logs
                </button>
              </div>
              {trip.days.map((day, i) => (
                <div
                  key={day.date}
                  className="log-day reveal"
                  style={{ '--delay': `${0.22 + i * 0.06}s` }}
                >
                  <div className="log-day-label">
                    <span>Day {i + 1}</span>
                    <time dateTime={day.date}>
                      {new Date(day.date + 'T12:00:00').toLocaleDateString(undefined, {
                        weekday: 'long',
                        month: 'long',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </time>
                    <span className="log-day-miles">
                      {Number(day.miles_driving || 0).toFixed(0)} mi driving
                    </span>
                  </div>
                  <LogSheet
                    day={day}
                    tripMeta={{
                      from: trip.waypoints?.current?.label,
                      to: trip.waypoints?.dropoff?.label,
                      carrier: 'Assessment Carrier LLC',
                      office: 'Home Terminal, USA',
                      vehicle: 'Unit 101 / Trailer T-205',
                    }}
                  />
                </div>
              ))}
            </section>
          </div>
        )}
      </main>

      <footer className="site-footer">
        <span>Property-carrying · 70 hrs / 8 days · FMCSA HOS</span>
        <span className="footer-sep" aria-hidden="true">
          ·
        </span>
        <span>Home terminal time</span>
      </footer>
    </div>
  )
}
