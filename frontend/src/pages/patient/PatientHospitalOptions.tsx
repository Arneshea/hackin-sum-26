import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'
import { subscribeToTable } from '../../services/realtime.js'

const STATUS_BADGE = {
  PENDING: 'pending',
  ACCEPTED: 'good',
  DECLINED: 'bad',
  WITHDRAWN: 'neutral',
  EXPIRED: 'neutral',
}

export default function PatientHospitalOptions() {
  const [requestId] = useLocalState('demo.requestId', null)
  const [, setTransportMode] = useLocalState('demo.transportMode', null)
  const [requestData, setRequestData] = useState(null)
  const [realtimeStatus, setRealtimeStatus] = useState('UNCONFIGURED')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [selectedHospitalId, setSelectedHospitalId] = useState(null)
  const [showTransportModal, setShowTransportModal] = useState(false)
  const navigate = useNavigate()

  async function refresh() {
    if (!requestId) return
    try {
      const data = await api.getPatientRequest(requestId)
      setRequestData(data)
      if (data.status === 'MATCHED') {
        navigate('/patient/journey')
      }
    } catch (err) {
      setError('Could not load request status')
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 4000)
    const unsubscribe = subscribeToTable({
      table: 'patient_request_responses',
      filter: `request_id=eq.${requestId}`,
      onChange: refresh,
      onStatusChange: setRealtimeStatus,
    })
    return () => {
      clearInterval(interval)
      unsubscribe()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId])

  // Step 1: patient taps "Select this hospital" → show transport modal
  function promptTransport(hospitalId) {
    setSelectedHospitalId(hospitalId)
    setShowTransportModal(true)
  }

  // Step 2: patient picks ambulance or self-drive → confirm selection
  async function handleSelectWithMode(mode) {
    setShowTransportModal(false)
    setTransportMode(mode)
    setError(null)
    setBusy(true)
    try {
      await api.selectHospital(requestId, selectedHospitalId)
      await refresh()
    } catch (err) {
      setError(err?.response?.data?.error || 'Selection failed')
    } finally {
      setBusy(false)
    }
  }

  if (!requestId) {
    return (
      <div className="panel">
        <p>No active request yet.</p>
        <button onClick={() => navigate('/patient/assessment')}>Start an assessment</button>
      </div>
    )
  }

  if (!requestData) return <p>Loading…</p>

  const acceptedResponses = requestData.responses.filter((r) => r.status === 'ACCEPTED')

  return (
    <div>
      <h2>Hospital Options</h2>
      <p className="subtitle">
        Request <span className="mono">{requestId}</span> — status{' '}
        <span className="badge neutral">{requestData.status}</span>
      </p>
      {realtimeStatus !== 'SUBSCRIBED' && realtimeStatus !== 'UNCONFIGURED' && (
        <div className="warning-banner">Live updates reconnecting — refreshing from the server every few seconds.</div>
      )}
      {error && <div className="error-banner">{error}</div>}

      {/* Transport mode modal */}
      {showTransportModal && (
        <div className="transport-modal-overlay">
          <div className="transport-modal">
            <h3>How will you get there?</h3>
            <p className="subtitle" style={{ marginBottom: 24 }}>
              Choose your transport to the selected hospital. This helps the hospital prepare for your arrival.
            </p>
            <div className="transport-options">
              <button
                className="transport-btn ambulance"
                onClick={() => handleSelectWithMode('AMBULANCE')}
              >
                <span className="transport-icon">🚑</span>
                <span className="transport-label">Request Ambulance</span>
                <span className="transport-desc">Emergency services will come to you</span>
              </button>
              <button
                className="transport-btn selfdrive"
                onClick={() => handleSelectWithMode('SELF_DRIVE')}
              >
                <span className="transport-icon">🚗</span>
                <span className="transport-label">Self-Drive / Walk</span>
                <span className="transport-desc">You'll make your own way there</span>
              </button>
            </div>
            <button
              className="secondary"
              style={{ marginTop: 16, width: '100%' }}
              onClick={() => setShowTransportModal(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="panel">
        <h3>Hospitals contacted</h3>
        {requestData.responses.length === 0 && <p>No hospitals were within range for this request.</p>}
        {requestData.responses.map((r) => (
          <div className="list-row" key={r.id}>
            <div>
              <strong>{r.hospital_name}</strong>
              <div className="mono">
                {r.travel_seconds_optional != null
                  ? `${Math.round(r.travel_seconds_optional / 60)} min estimated travel`
                  : 'travel estimate unavailable'}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className={`badge ${STATUS_BADGE[r.status] || 'neutral'}`}>{r.status}</span>
              {r.status === 'ACCEPTED' && requestData.status === 'PATIENT_SELECTING' && (
                <button disabled={busy} onClick={() => promptTransport(r.hospital_id)}>
                  Select this hospital
                </button>
              )}
              {r.status === 'ACCEPTED' && requestData.selected_hospital_id_optional === r.hospital_id && (
                <span className="badge good">Selected — awaiting confirmation</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {requestData.status === 'BROADCASTING' && (
        <p className="footnote">Waiting for hospitals to respond to the request…</p>
      )}
      {requestData.status === 'NO_MATCH' && (
        <div className="error-banner">No hospitals responded. Please seek emergency care directly or contact emergency services.</div>
      )}
      {acceptedResponses.length === 0 && requestData.status === 'BROADCASTING' && (
        <p className="footnote">No hospital has accepted yet.</p>
      )}
    </div>
  )
}
