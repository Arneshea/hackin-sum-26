import { useLocation, useNavigate } from 'react-router-dom'

export default function EmergencyStatus() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location.state

  if (!result) {
    return (
      <div className="panel">
        <p>No active emergency dispatch.</p>
        <button onClick={() => navigate('/patient')}>Back to Patient Home</button>
      </div>
    )
  }

  return (
    <div>
      <h2>Emergency Dispatch</h2>

      {result.status === 'DISPATCHED' && (
        <div className="panel" style={{ borderColor: 'var(--green)' }}>
          <div className="warning-banner" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>
            Ambulance dispatched from <strong>{result.hospital?.name}</strong>.
          </div>
          <p>
            Estimated arrival: {result.eta_seconds != null ? `${Math.round(result.eta_seconds / 60)} min` : 'unavailable'}
            {result.eta_source && result.eta_source !== 'OSRM' ? ' (distance-based estimate)' : ''}
          </p>
          <p className="footnote">{result.warning}</p>
          <button onClick={() => navigate('/patient/journey')}>Track journey</button>
        </div>
      )}

      {result.status === 'NO_HOSPITAL_FOUND' && (
        <div className="error-banner">{result.warning}</div>
      )}

      {result.status === 'ERROR' && (
        <div className="error-banner">{result.warning}</div>
      )}
    </div>
  )
}
