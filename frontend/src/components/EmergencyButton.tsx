import { useNavigate } from 'react-router-dom'

/**
 * No form, no triage questions — one tap goes to a countdown screen
 * (EmergencyCountdown.jsx) which dispatches automatically after 5
 * seconds, or immediately on Cancel. The actual dispatch call and
 * geolocation capture happen there, not here.
 */
export default function EmergencyButton() {
  const navigate = useNavigate()

  return (
    <button className="emergency-button" onClick={() => navigate('/patient/emergency-countdown')}>
      <span className="dot" />
      Emergency — Dispatch Ambulance
    </button>
  )
}