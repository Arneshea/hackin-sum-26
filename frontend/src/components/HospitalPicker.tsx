import { useEffect, useState } from 'react'
import { api } from '../services/api.js'

/**
 * Auth (Phase 10 / section 19) is deliberately out of scope for this
 * build pass, per section 9's build order ("add after the core
 * workflow is functional"). This picker stands in for "log in as
 * hospital-staff at hospital X" so the demo can be driven from
 * separate browser windows per section 30 without wiring up Supabase
 * Auth yet.
 */
export default function HospitalPicker({ hospitalId, onChange }) {
  const [hospitals, setHospitals] = useState([])

  useEffect(() => {
    api.listHospitals().then(setHospitals).catch(() => setHospitals([]))
  }, [])

  return (
    <div className="panel" style={{ marginBottom: 16 }}>
      <label style={{ marginTop: 0 }}>Acting as hospital staff at</label>
      <select value={hospitalId || ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a hospital…</option>
        {hospitals.map((h) => (
          <option key={h.id} value={h.id}>{h.name}</option>
        ))}
      </select>
      <p className="footnote">Demo stand-in for hospital-staff auth, not yet implemented in this build pass.</p>
    </div>
  )
}
