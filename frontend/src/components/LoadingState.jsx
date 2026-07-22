export default function LoadingState() {
  return (
    <div className="loading-panel" aria-live="polite">
      <div className="loading-track">
        <div className="loading-truck" />
      </div>
      <p>Geocoding locations and building a legal schedule…</p>
      <p className="loading-sub">Routing + HOS planning usually takes a few seconds.</p>
    </div>
  )
}
