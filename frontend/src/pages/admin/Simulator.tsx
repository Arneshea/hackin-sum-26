import { useState } from 'react'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'

const DEMO_HOSPITALS = [
  { id: '11111111-1111-1111-1111-111111111111', name: 'Hospital A (Demo)' },
  { id: '22222222-2222-2222-2222-222222222222', name: 'Hospital B (Demo)' },
  { id: '33333333-3333-3333-3333-333333333333', name: 'Hospital C (Demo)' },
]

export default function Simulator() {
  const [token, setToken] = useLocalState('demo.adminToken', import.meta.env.VITE_DEMO_ADMIN_TOKEN || '')
  const [hospitalId, setHospitalId] = useState(DEMO_HOSPITALS[0].id)
  const [resourceType, setResourceType] = useState('ICU')
  const [measurementType, setMeasurementType] = useState('COUNT')
  const [status, setStatus] = useState('AVAILABLE')
  const [availableCount, setAvailableCount] = useState(2)
  const [totalCount, setTotalCount] = useState(10)
  const [log, setLog] = useState([])
  const [busy, setBusy] = useState(false)

  function appendLog(line) {
    setLog((prev) => [`${new Date().toLocaleTimeString()} — ${line}`, ...prev].slice(0, 20))
  }

  async function handleSet(e) {
    e?.preventDefault()
    setBusy(true)
    try {
      const result = await api.simulatorSetHospitalState(
        {
          hospital_id: hospitalId,
          resource_type: resourceType,
          measurement_type: measurementType,
          status,
          available_count_optional: measurementType === 'COUNT' ? Number(availableCount) : null,
          total_count_optional: measurementType === 'COUNT' ? Number(totalCount) : null,
        },
        token
      )
      appendLog(`Set ${resourceType} on hospital ${hospitalId.slice(0, 8)} → ${status}${measurementType === 'COUNT' ? ` (${availableCount}/${totalCount})` : ''} — applied=${result.applied}, v${result.new_version}`)
    } catch (err) {
      appendLog(`ERROR: ${err?.response?.data?.error || 'request failed'}`)
    } finally {
      setBusy(false)
    }
  }

  async function runCoreDemoScenario() {
    setBusy(true)
    appendLog('Running section 28 core demo scenario: Hospital A ICU 2 → 1 → 0…')
    try {
      await api.simulatorSetHospitalState(
        { hospital_id: DEMO_HOSPITALS[0].id, resource_type: 'ICU', measurement_type: 'COUNT', status: 'AVAILABLE', available_count_optional: 1, total_count_optional: 10 },
        token
      )
      appendLog('Hospital A ICU → 1 (still feasible)')
      await new Promise((r) => setTimeout(r, 2500))
      await api.simulatorSetHospitalState(
        { hospital_id: DEMO_HOSPITALS[0].id, resource_type: 'ICU', measurement_type: 'COUNT', status: 'UNAVAILABLE', available_count_optional: 0, total_count_optional: 10 },
        token
      )
      appendLog('Hospital A ICU → 0 (now infeasible — open a referral evaluation to see the rerank)')
    } catch (err) {
      appendLog(`ERROR: ${err?.response?.data?.error || 'request failed'}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h2>Hospital State Simulator</h2>
      <p className="subtitle">
        The only path allowed to write arbitrary hospital state, gated by a demo admin token (section 41V).
        Goes through the same <span className="mono">apply_hospital_state_update</span> function a real
        hospital adapter would use (step 2.9) — no simulator-only shortcut.
      </p>

      <div className="panel">
        <label>Demo admin token</label>
        <input value={token} onChange={(e) => setToken(e.target.value)} />
      </div>

      <div className="panel">
        <h3>Section 28 core demo scenario</h3>
        <p className="footnote">Hospital A ICU available 2 → 1 → 0, live, to demonstrate rerank.</p>
        <button disabled={busy} onClick={runCoreDemoScenario}>Run scenario</button>
      </div>

      <form className="panel" onSubmit={handleSet}>
        <h3>Manual state update</h3>
        <div className="grid-2">
          <div>
            <label>Hospital</label>
            <select value={hospitalId} onChange={(e) => setHospitalId(e.target.value)}>
              {DEMO_HOSPITALS.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div>
            <label>Resource type</label>
            <input value={resourceType} onChange={(e) => setResourceType(e.target.value)} />
          </div>
        </div>
        <div className="grid-2">
          <div>
            <label>Measurement type</label>
            <select value={measurementType} onChange={(e) => setMeasurementType(e.target.value)}>
              <option value="COUNT">COUNT</option>
              <option value="BINARY_SERVICE">BINARY_SERVICE</option>
              <option value="PERSONNEL_AVAILABILITY">PERSONNEL_AVAILABILITY</option>
            </select>
          </div>
          <div>
            <label>Status</label>
            <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="AVAILABLE / UNAVAILABLE / OPERATIONAL / ON_CALL" />
          </div>
        </div>
        {measurementType === 'COUNT' && (
          <div className="grid-2">
            <div>
              <label>Available count</label>
              <input type="number" value={availableCount} onChange={(e) => setAvailableCount(Number(e.target.value))} />
            </div>
            <div>
              <label>Total count</label>
              <input type="number" value={totalCount} onChange={(e) => setTotalCount(Number(e.target.value))} />
            </div>
          </div>
        )}
        <div style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy}>Apply state update</button>
        </div>
      </form>

      <div className="panel">
        <h3>Log</h3>
        {log.length === 0 && <p className="footnote">No actions yet.</p>}
        {log.map((line, i) => <div key={i} className="mono" style={{ marginBottom: 4 }}>{line}</div>)}
      </div>
    </div>
  )
}
