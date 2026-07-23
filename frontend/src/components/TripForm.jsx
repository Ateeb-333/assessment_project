import { useState } from 'react'

const defaultForm = {
  current_location: 'Chicago, IL',
  pickup_location: 'Des Moines, IA',
  dropoff_location: 'Denver, CO',
  current_cycle_used: 12.5,
  start_datetime: '',
}

export default function TripForm({ onSubmit, loading }) {
  const [form, setForm] = useState(defaultForm)

  function update(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    const payload = {
      current_location: form.current_location.trim(),
      pickup_location: form.pickup_location.trim(),
      dropoff_location: form.dropoff_location.trim(),
      current_cycle_used: Number(form.current_cycle_used),
    }
    if (form.start_datetime) {
      payload.start_datetime = new Date(form.start_datetime).toISOString()
    }
    onSubmit(payload)
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit}>
      <div className="form-intro">
        <h3>Trip details</h3>
        <p>City and state work best. Cycle hours already used in your 70/8 window.</p>
      </div>
      <div className="form-grid">
        <label>
          <span>Current location</span>
          <input
            required
            value={form.current_location}
            onChange={(e) => update('current_location', e.target.value)}
            placeholder="Chicago, IL"
            autoComplete="off"
          />
        </label>
        <label>
          <span>Pickup location</span>
          <input
            required
            value={form.pickup_location}
            onChange={(e) => update('pickup_location', e.target.value)}
            placeholder="Des Moines, IA"
            autoComplete="off"
          />
        </label>
        <label>
          <span>Dropoff location</span>
          <input
            required
            value={form.dropoff_location}
            onChange={(e) => update('dropoff_location', e.target.value)}
            placeholder="Denver, CO"
            autoComplete="off"
          />
        </label>
        <label>
          <span>Cycle used (hrs)</span>
          <input
            required
            type="number"
            min="0"
            max="70"
            step="0.1"
            value={form.current_cycle_used}
            onChange={(e) => update('current_cycle_used', e.target.value)}
          />
        </label>
        <label className="span-2">
          <span>Start datetime — optional</span>
          <input
            type="datetime-local"
            value={form.start_datetime}
            onChange={(e) => update('start_datetime', e.target.value)}
          />
        </label>
      </div>
      <button type="submit" className="btn-primary" disabled={loading}>
        <span>{loading ? 'Planning…' : 'Plan trip'}</span>
        {!loading && <span className="btn-arrow" aria-hidden="true">→</span>}
      </button>
    </form>
  )
}
