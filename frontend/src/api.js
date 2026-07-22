const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export async function createTrip(payload) {
  const res = await fetch(`${API_BASE}/api/trips/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  })

  let data
  try {
    data = await res.json()
  } catch {
    throw new Error('Server returned an unexpected response')
  }

  if (!res.ok) {
    throw new Error(data.detail || data.error || 'Could not plan this trip')
  }
  return data
}
