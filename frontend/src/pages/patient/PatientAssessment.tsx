import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'

const PRESENTING_CONCERNS = [
  { key: 'SUSPECTED_STROKE', label: 'Suspected stroke symptoms (facial droop, slurred speech, weakness)' },
  { key: 'SEVERE_TRAUMA', label: 'Severe trauma / major injury' },
  { key: 'CARDIAC_SYMPTOMS', label: 'Chest pain / suspected cardiac event' },
  { key: 'GENERAL_EMERGENCY', label: 'Other general emergency' },
]

export default function PatientAssessment() {
  const [patientId] = useLocalState('demo.patientId', null)
  const [requesterRole] = useLocalState('demo.requesterRole', 'PATIENT')
  const [, setRequestId] = useLocalState('demo.requestId', null)
  const [, setJourneyId] = useLocalState('demo.journeyId', null)
  const [, setPatientLat] = useLocalState('demo.patientLat', null)
  const [, setPatientLon] = useLocalState('demo.patientLon', null)

  const [rawInput, setRawInput] = useState('')
  const [concerns, setConcerns] = useState([])
  const [lat, setLat] = useState('28.6200')
  const [lon, setLon] = useState('77.2100')
  const [geoLoading, setGeoLoading] = useState(false)
  const [assessment, setAssessment] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  function toggleConcern(key) {
    setConcerns((prev) => (prev.includes(key) ? prev.filter((c) => c !== key) : [...prev, key]))
  }

  function handleGeolocate() {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.')
      return
    }
    setGeoLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(6))
        setLon(pos.coords.longitude.toFixed(6))
        setGeoLoading(false)
      },
      () => {
        setError('Could not get your location. Please enter coordinates manually.')
        setGeoLoading(false)
      },
      { timeout: 8000 },
    )
  }

  async function handleAssess(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const result = await api.createAssessment({
        patient_id: patientId,
        raw_input: rawInput,
        presenting_concerns: concerns,
        requester_role_optional: requesterRole,
      })
      setAssessment(result)
    } catch (err) {
      setError(err?.response?.data?.error || 'Assessment failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleSubmitRequest() {
    setError(null)
    setBusy(true)
    try {
      const result = await api.createPatientRequest({
        patient_id: patientId,
        location_lat: Number(lat),
        location_lon: Number(lon),
        urgency: assessment.triage_label,
        symptom_summary: rawInput,
        requirements: assessment.requirements,
        requester_role_optional: requesterRole,
      })
      // Store patient coords so journey map can draw routes
      setPatientLat(Number(lat))
      setPatientLon(Number(lon))
      setRequestId(result.request_id)
      setJourneyId(result.journey_id)
      navigate('/patient/options')
    } catch (err) {
      setError(err?.response?.data?.error || 'Could not submit request')
    } finally {
      setBusy(false)
    }
  }

  if (!patientId) {
    return (
      <div className="panel">
        <p>No demo patient selected yet.</p>
        <button onClick={() => navigate('/patient')}>Go to Patient Home</button>
      </div>
    )
  }

  return (
    <div>
      <h2>Assessment</h2>
      <p className="subtitle">
        A broad Stage-1 pre-triage signal, not a diagnosis (step 4.4). If the model is unavailable,
        this will show <span className="mono">ASSESSMENT_UNAVAILABLE</span> rather than guessing.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <form className="panel" onSubmit={handleAssess}>
        <label>Describe the symptoms / situation</label>
        <textarea value={rawInput} onChange={(e) => setRawInput(e.target.value)} required
          placeholder="e.g. sudden weakness on one side, difficulty speaking, started 20 minutes ago" />

        <label>Presenting concern (explicit selection — never inferred from the text above, step 4.7)</label>
        {PRESENTING_CONCERNS.map((c) => (
          <div className="checkbox-row" key={c.key}>
            <input type="checkbox" id={c.key} checked={concerns.includes(c.key)} onChange={() => toggleConcern(c.key)} />
            <label htmlFor={c.key} style={{ margin: 0 }}>{c.label}</label>
          </div>
        ))}

        <label>Your location</label>
        <div className="grid-2" style={{ alignItems: 'flex-end' }}>
          <div>
            <label style={{ marginTop: 0 }}>Latitude</label>
            <input value={lat} onChange={(e) => setLat(e.target.value)} />
          </div>
          <div>
            <label style={{ marginTop: 0 }}>Longitude</label>
            <input value={lon} onChange={(e) => setLon(e.target.value)} />
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <button type="button" className="secondary" onClick={handleGeolocate} disabled={geoLoading}>
            {geoLoading ? '📍 Detecting…' : '📍 Use my current location'}
          </button>
        </div>
        <p className="footnote">
          Only used internally for candidate matching/routing — exact coordinates are not shown to
          the network broadcast list until a hospital has responded (step 4.8).
        </p>

        <div style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy}>{busy ? 'Assessing…' : 'Run Stage-1 assessment'}</button>
        </div>
      </form>

      {assessment && (
        <div className="panel">
          <h3>Assessment result</h3>
          {assessment.triage_label === 'ASSESSMENT_UNAVAILABLE' ? (
            <div className="warning-banner">
              Automated assessment is unavailable right now. Following the manual-triage fallback path —
              your request will still be submitted for hospital matching.
            </div>
          ) : (
            <p>
              Triage signal: <span className="badge neutral">{assessment.triage_label}</span>{' '}
              → care pathway <span className="badge neutral">{assessment.care_pathway}</span>
            </p>
          )}
          <p className="mono">
            model: {assessment.model_name} @ {assessment.model_version} · policy {assessment.policy_version}
          </p>
          <h3 style={{ marginTop: 14 }}>Required capabilities for hospital matching</h3>
          <ul className="explanation-list">
            {assessment.requirements.map((r) => (
              <li key={r.requirement_type}>{r.requirement_type} {r.mandatory ? '(mandatory)' : '(optional)'}</li>
            ))}
          </ul>
          <div style={{ marginTop: 16 }}>
            <button onClick={handleSubmitRequest} disabled={busy}>
              {busy ? 'Submitting…' : 'Submit request to nearby hospitals'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
