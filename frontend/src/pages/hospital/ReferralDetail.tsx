import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'

import { api } from '../../services/api.js'

const DECLINE_REASONS = ['ICU_UNAVAILABLE', 'SPECIALIST_UNAVAILABLE', 'DIAGNOSTIC_UNAVAILABLE', 'CAPACITY_UNAVAILABLE', 'OTHER']

export default function ReferralDetail() {
  const { referralId } = useParams()
  const location = useLocation()
  const hospitalId = location.state?.hospitalId

  const [referral, setReferral] = useState(null)
  const [journey, setJourney] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [declineReason, setDeclineReason] = useState('CAPACITY_UNAVAILABLE')

  async function refresh() {
    try {
      const r = await api.getReferral(referralId)
      setReferral(r)
      if (r.journey_id) {
        const j = await api.getJourney(r.journey_id)
        setJourney(j)
      }
    } catch {
      setError('Could not load referral')
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 4000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [referralId])

  async function handleAccept() {
    setBusy(true)
    setError(null)
    try {
      await api.acceptReferral(referralId, hospitalId)
      await refresh()
    } catch (err) {
      setError(err?.response?.data?.error || 'Another hospital may have already accepted this referral')
    } finally {
      setBusy(false)
    }
  }

  async function handleDecline() {
    setBusy(true)
    setError(null)
    try {
      await api.declineReferral(referralId, hospitalId, declineReason)
      await refresh()
    } catch (err) {
      setError(err?.response?.data?.error || 'Decline failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleReceived() {
    setBusy(true)
    try {
      await api.markReceived(journey.transfer.id)
      await refresh()
    } catch (err) {
      setError(err?.response?.data?.error || 'Could not mark received')
    } finally {
      setBusy(false)
    }
  }

  const [handoffForm, setHandoffForm] = useState({ clinical_summary: '', current_condition: '', referring_doctor: '' })

  async function handleCompleteHandoff() {
    setBusy(true)
    try {
      await api.completeHandoff(journey.transfer.id, handoffForm)
      await refresh()
    } catch (err) {
      setError(err?.response?.data?.error || 'Could not complete handoff')
    } finally {
      setBusy(false)
    }
  }

  if (!referral) return <p>Loading…</p>

  const myResponse = referral.responses.find((r) => r.hospital_id === hospitalId)

  return (
    <div>
      <h2>Referral Detail</h2>
      <p className="subtitle mono">{referral.id}</p>
      {error && <div className="error-banner">{error}</div>}

      <div className="panel">
        <h3>Clinical summary</h3>
        <p><strong>Reason:</strong> {referral.reason_for_referral}</p>
        <p>{referral.clinical_summary}</p>
        <p>Urgency: <span className="badge neutral">{referral.urgency}</span></p>
        <h3 style={{ marginTop: 14 }}>Requirements</h3>
        <ul className="explanation-list">
          {referral.requirements.map((r) => <li key={r.id}>{r.requirement_type}{r.mandatory ? ' (mandatory)' : ''}</li>)}
        </ul>
      </div>

      {myResponse?.status === 'PENDING' && referral.status === 'PENDING_ACCEPTANCE' && (
        <div className="panel">
          <h3>Respond</h3>
          <button disabled={busy} onClick={handleAccept}>Accept — coordinate receipt of this patient</button>{' '}
          <select value={declineReason} onChange={(e) => setDeclineReason(e.target.value)} style={{ display: 'inline-block', width: 220 }}>
            {DECLINE_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>{' '}
          <button className="secondary" disabled={busy} onClick={handleDecline}>Decline</button>
          <p className="footnote">
            Accepting is a coordination acknowledgement, not a claim that a bed is physically reserved (step 5.6).
          </p>
        </div>
      )}

      {referral.status === 'ACCEPTED' && journey?.transfer && (
        <div className="panel">
          <h3>Transfer</h3>
          <p>Status: <span className="badge neutral">{journey.transfer.status}</span></p>
          {journey.transfer.status === 'EN_ROUTE' && (
            <button disabled={busy} onClick={handleReceived}>Mark patient received</button>
          )}
          {journey.transfer.status === 'PATIENT_RECEIVED' && (
            <div>
              <h4 style={{ fontSize: 13.5 }}>Complete handoff</h4>
              <label>Clinical summary</label>
              <textarea value={handoffForm.clinical_summary} onChange={(e) => setHandoffForm({ ...handoffForm, clinical_summary: e.target.value })} />
              <label>Current condition</label>
              <input value={handoffForm.current_condition} onChange={(e) => setHandoffForm({ ...handoffForm, current_condition: e.target.value })} />
              <label>Referring doctor</label>
              <input value={handoffForm.referring_doctor} onChange={(e) => setHandoffForm({ ...handoffForm, referring_doctor: e.target.value })} />
              <div style={{ marginTop: 12 }}>
                <button disabled={busy} onClick={handleCompleteHandoff}>Complete handoff</button>
              </div>
            </div>
          )}
          {journey.transfer.status === 'HANDOFF_COMPLETED' && (
            <div className="warning-banner" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>
              Handoff completed. Journey closed.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
