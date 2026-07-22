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
    <div className="app">
      <div className="atmosphere" aria-hidden="true" />

      <header className="site-header">
        <div className="brand">
          <span className="brand-mark">ELD</span>
          <div>
            <h1>Trip Planner</h1>
            <p>Legal schedules · route map · DOT daily logs</p>
          </div>
        </div>
      </header>

      <main>
        {!trip && !loading && (
          <section className="hero-panel">
            <div className="hero-copy">
              <h2>Plan a compliant trip</h2>
              <p>
                Enter current, pickup, and dropoff locations. We compute FMCSA
                Hours-of-Service stops and draw your daily log sheets.
              </p>
            </div>
            <TripForm onSubmit={handleSubmit} loading={loading} />
          </section>
        )}

        {loading && <LoadingState />}

        {error && !loading && (
          <div className="error-banner" role="alert">
            <strong>Could not plan trip.</strong> {error}
            <button type="button" className="btn-ghost" onClick={() => setError('')}>
              Dismiss
            </button>
          </div>
        )}

        {trip && !loading && (
          <>
            <TripSummary trip={trip} onReset={reset} />

            <section className="map-section">
              <h2>Route &amp; stops</h2>
              <p className="section-lede">
                Fuel, rest, break, pickup, and dropoff markers along the drive.
              </p>
              <RouteMap trip={trip} />
            </section>

            <StopsTimeline trip={trip} />

            <section className="logs-section">
              <h2>Daily log sheets</h2>
              <p className="section-lede">
                FMCSA-style Drivers Daily Log — grid, remarks, miles, and 70/8 recap. Totals always sum to 24.00.
              </p>
              {trip.days.map((day) => (
                <LogSheet
                  key={day.date}
                  day={day}
                  tripMeta={{
                    from: trip.waypoints?.current?.label,
                    to: trip.waypoints?.dropoff?.label,
                    carrier: 'Assessment Carrier LLC',
                    office: 'Home Terminal, USA',
                    vehicle: 'Unit 101 / Trailer T-205',
                  }}
                />
              ))}
            </section>
          </>
        )}
      </main>

      <footer className="site-footer">
        <span>Property-carrying · 70 hrs / 8 days · FMCSA HOS</span>
      </footer>
    </div>
  )
}
