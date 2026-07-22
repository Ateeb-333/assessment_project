import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { useEffect } from 'react'
import 'leaflet/dist/leaflet.css'

const stopColors = {
  pickup: '#1a6b4a',
  dropoff: '#8b3a2a',
  fuel: '#b45309',
  break: '#1d4ed8',
  rest: '#5b21b6',
  restart: '#0f172a',
}

function makeIcon(color) {
  return L.divIcon({
    className: 'stop-marker',
    html: `<span style="background:${color}"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  })
}

function FitBounds({ positions }) {
  const map = useMap()
  useEffect(() => {
    if (!positions?.length) return
    const bounds = L.latLngBounds(positions)
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [map, positions])
  return null
}

export default function RouteMap({ trip }) {
  if (!trip?.route?.geometry?.length) {
    return <div className="map-empty">Plan a trip to see the route.</div>
  }

  const geometry = trip.route.geometry
  const stops = (trip.stops || []).filter((s) => s.lat != null && s.lng != null)

  return (
    <div className="map-wrap">
      <MapContainer
        center={geometry[0]}
        zoom={5}
        scrollWheelZoom
        className="route-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polyline positions={geometry} pathOptions={{ color: '#1a6b4a', weight: 4, opacity: 0.85 }} />
        <FitBounds positions={geometry} />
        {stops.map((stop, i) => (
          <Marker
            key={`${stop.type}-${i}`}
            position={[stop.lat, stop.lng]}
            icon={makeIcon(stopColors[stop.type] || '#334155')}
          >
            <Popup>
              <strong>{stop.type}</strong>
              <div>{stop.label}</div>
              <div>{new Date(stop.arrival).toLocaleString()}</div>
              <div>{stop.duration_hours}h</div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <ul className="map-legend">
        {Object.entries(stopColors).map(([k, c]) => (
          <li key={k}>
            <i style={{ background: c }} />
            {k}
          </li>
        ))}
      </ul>
    </div>
  )
}
