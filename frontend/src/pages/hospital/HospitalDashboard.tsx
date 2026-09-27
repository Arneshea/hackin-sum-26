import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'
import HospitalPicker from '../../components/HospitalPicker.jsx'

/**
 * Product decision (see docs/DECISIONS.md): hospitals no longer
 * create Stage-2 referrals — patients bring their own (scanned or
 * manually entered). This dashboard therefore only covers what a
 * hospital actually still does: respond to incoming Stage-1 patient
 * requests, progress a patient's care once they arrive, respond to
 * incoming Stage-2 referrals a patient has sent them, and manage the
 * transfer/handoff once accepted. Hospital1Dashboard.jsx and
 * ReceivingDashboard.jsx from the previous pass are merged into this
 * one screen since a real hospital plays both roles.
 */
export default function HospitalDashboard() {
  const [hospitalId, setHospitalId] = useLocalState('demo.actingHospitalId', null)
  const [tab, setTab] = useState('requests')
  const [responses, setResponses] = useState([])
  const [journeys, setJourneys] = useState([])
  const [referralResponses, setReferralResponses] = useState([])
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  async function refresh() {
    if (!hospitalId) return
    try {
      const [r, j, rr] = await Promise.all([
        api.listHospitalRequestResponses(hospitalId),
        api.listHospitalJourneys(hospitalId),
        api.listHospitalReferralResponses(hospitalId),
      ])
      setResponses(r)
      setJourneys(j)
      setReferralResponses(rr)
    } catch {
      setError('Could not load dashboard data')
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hospitalId])

  async function act(fn, id) {
    setBusyId(id)
    setError(null)
    try {
      await fn()
      await refresh()
    } catch (err) {
      setError(err?.response?.data?.error || 'Action failed')
    } finally {
      setBusyId(null)
    }
  }

  const patientsOnPath = journeys.filter((j) => j.stage1_hospital_id === hospitalId)
  const incomingReferralsCount = referralResponses.filter((r) => r.status === 'PENDING').length
  const incomingRequestsCount = responses.filter((r) => r.status === 'PENDING').length

  return (
    <div>
      <h2>Hospital Dashboard</h2>
      <p className="subtitle">
        Referrals are now started by the patient, not by this hospital (see docs/DECISIONS.md) — this
        dashboard responds to what patients send you, and progresses care/transfers.
      </p>

      <HospitalPicker hospitalId={hospitalId} onChange={setHospitalId} />
      {error && <div className="error-banner">{error}</div>}
      {!hospitalId && <p>Select a hospital above to see its dashboard.</p>}

      {hospitalId && (
        <>
          <div className="tab-row">
            <button className={tab === 'requests' ? 'active' : ''} onClick={() => setTab('requests')}>
              Stage-1 Requests {incomingRequestsCount > 0 ? `(${incomingRequestsCount})` : ''}
            </button>
            <button className={tab === 'patients' ? 'active' : ''} onClick={() => setTab('patients')}>
              Active Patients
            </button>
            <button className={tab === 'referrals' ? 'active' : ''} onClick={() => setTab('referrals')}>
              Incoming Referrals {incomingReferralsCount > 0 ? `(${incomingReferralsCount})` : ''}
            </button>
          </div>

          {tab === 'requests' && (
            <div className="panel">
              <h3>Incoming Stage-1 requests</h3>
              {responses.length === 0 && <p className="footnote">No requests yet.</p>}
              {responses.map((r) => (
                <div className="list-row" key={r.id}>
                  <div>
                    <strong>{r.urgency}</strong> — {r.symptom_summary || '(no summary)'}
                    <div className="mono">request status: {r.request_status}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`badge ${r.status === 'ACCEPTED' ? 'good' : r.status === 'DECLINED' ? 'bad' : 'pending'}`}>{r.status}</span>
                    {r.status === 'PENDING' && (
                      <>
                        <button disabled={busyId === r.id} onClick={() => act(() => api.acceptResponse(r.id), r.id)}>Accept</button>
                        <button className="secondary" disabled={busyId === r.id} onClick={() => act(() => api.declineResponse(r.id, 'CAPACITY_UNAVAILABLE'), r.id)}>Decline</button>
                      </>
                    )}
                    {r.status === 'ACCEPTED' && (
                      <button disabled={busyId === r.id} onClick={() => act(() => api.confirmSelection(r.id, true), r.id)}>
                        Confirm (if patient selected you)
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 'patients' && (
            <div className="panel">
              <h3>Patients on this hospital's path</h3>
              {patientsOnPath.length === 0 && <p className="footnote">No active patients yet.</p>}
              {patientsOnPath.map((j) => (
                <div className="list-row" key={j.journey_id}>
                  <div>
                    <strong>{j.patient_display_name}</strong>
                    <div className="mono">{j.journey_id}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="badge neutral">{j.current_status}</span>
                    {j.current_status === 'MATCHED_TO_HOSPITAL_1' && (
                      <button onClick={() => act(() => api.markEnRoute(j.journey_id), j.journey_id)}>Mark en route</button>
                    )}
                    {j.current_status === 'EN_ROUTE_TO_HOSPITAL_1' && (
                      <button onClick={() => act(() => api.markArrived(j.journey_id), j.journey_id)}>Mark arrived</button>
                    )}
                    {j.current_status === 'ARRIVED_AT_HOSPITAL_1' && (
                      <button onClick={() => act(() => api.markUnderCare(j.journey_id), j.journey_id)}>Begin care</button>
                    )}
                    {j.current_status === 'UNDER_CARE' && (
                      <span className="badge neutral">Awaiting patient-initiated referral, if needed</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 'referrals' && (
            <div className="panel">
              <h3>Incoming referrals from patients</h3>
              {referralResponses.length === 0 && <p className="footnote">No referrals yet.</p>}
              {referralResponses.map((r) => (
                <div className="list-row" key={r.id}>
                  <div>
                    <strong>{r.reason_for_referral}</strong>
                    <div className="mono">
                      {r.initiated_by === 'PATIENT' ? 'self-referred by patient' : 'referred by hospital'}
                      {r.referring_doctor_name ? ` · Dr. ${r.referring_doctor_name}` : ''} · status {r.referral_status}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`badge ${r.status === 'ACCEPTED' ? 'good' : r.status === 'DECLINED' ? 'bad' : r.status === 'EXPIRED' ? 'neutral' : 'pending'}`}>
                      {r.status}
                    </span>
                    <button className="secondary" onClick={() => navigate(`/hospital/referral/${r.referral_id}`, { state: { hospitalId } })}>
                      View details
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
