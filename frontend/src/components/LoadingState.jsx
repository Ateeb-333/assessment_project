import { useEffect, useState } from 'react'

const STEPS = [
  'Geocoding locations…',
  'Building the highway route…',
  'Applying FMCSA HOS clocks…',
  'Drawing daily log sheets…',
]

export default function LoadingState() {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setStep((s) => (s + 1) % STEPS.length)
    }, 1600)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="loading-panel" aria-live="polite">
      <div className="loading-visual" aria-hidden="true">
        <div className="loading-road">
          <div className="loading-dash" />
        </div>
        <div className="loading-cab" />
      </div>
      <p className="loading-step">{STEPS[step]}</p>
      <p className="loading-sub">Usually a few seconds for routing and the HOS engine.</p>
    </div>
  )
}
