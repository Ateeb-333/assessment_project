const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function formatError(data) {
  if (!data || typeof data !== 'object') return 'Could not plan this trip'
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ')
  }
  // DRF field errors: { field: ["msg"] }
  const parts = []
  for (const [key, val] of Object.entries(data)) {
    if (key === 'detail' || key === 'error') continue
    if (Array.isArray(val)) parts.push(`${key}: ${val.join(', ')}`)
    else if (typeof val === 'string') parts.push(`${key}: ${val}`)
  }
  if (parts.length) return parts.join('; ')
  if (data.error) return String(data.error)
  return 'Could not plan this trip'
}

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
    throw new Error(formatError(data))
  }
  return data
}
