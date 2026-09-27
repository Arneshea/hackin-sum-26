import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'

export default function PatientHome() {
  const [patientId, setPatientId] = useLocalState('demo.patientId', null)
  const [displayName, setDisplayName] = useState('')
  const [age, setAge] = useState('')
  const [sex, setSex] = useState('')
  const [requesterRole, setRequesterRole] = useLocalState('demo.requesterRole', 'PATIENT')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function handleCreatePatient(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const result = await api.createPatient({ display_name: displayName, age: age ? Number(age) : null, sex })
      setPatientId(result.id)
    } catch (err) {
      setError(err?.response?.data?.error || 'Could not create patient record')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h2>Patient / Attendant</h2>
      <p className="subtitle">
        Start here whether you are the patient or an attendant acting on the patient's behalf
        (step 4.1) — the app never assumes the person typing is necessarily the patient.
      </p>

      {patientId ? (
        <div className="panel">
          <h3>Current demo patient</h3>
          <p className="mono">patient_id: {patientId}</p>
          <label>You are filling this out as</label>
          <select value={requesterRole} onChange={(e) => setRequesterRole(e.target.value)}>
            <option value="PATIENT">The patient</option>
            <option value="DOCTOR">An attendant / family member</option>
          </select>
          <div style={{ marginTop: 16 }}>
            <button onClick={() => navigate('/patient/assessment')}>Continue to assessment</button>{' '}
            <button className="secondary" onClick={() => setPatientId(null)}>Start over as a new patient</button>
          </div>
        </div>
      ) : (
        <form className="panel" onSubmit={handleCreatePatient}>
          <h3>Create a demo patient record</h3>
          <p className="footnote">Synthetic prototype data only (section 23) — do not enter real patient information.</p>
          {error && <div className="error-banner">{error}</div>}
          <label>Display name</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required placeholder="e.g. Demo Patient" />
          <div className="grid-2">
            <div>
              <label>Age</label>
              <input type="number" value={age} onChange={(e) => setAge(e.target.value)} />
            </div>
            <div>
              <label>Sex</label>
              <select value={sex} onChange={(e) => setSex(e.target.value)}>
                <option value="">Prefer not to say</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create patient record'}</button>
          </div>
        </form>
      )}
    </div>
  )
}
