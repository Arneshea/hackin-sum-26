import { useEffect, useRef, useState } from 'react'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'

const REQUIREMENT_OPTIONS = ['ICU', 'NEUROLOGY', 'CT', 'CARDIOLOGY', 'EMERGENCY']

export default function PatientReferral() {
  const [patientId] = useLocalState('demo.patientId', null)
  const [journeyId] = useLocalState('demo.journeyId', null)

  const [mode, setMode] = useState('scan') // 'scan' | 'manual'
  const [imagePreview, setImagePreview] = useState(null)
  const [imageBase64, setImageBase64] = useState(null)
  const [extraText, setExtraText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState(null)
  const [parseNote, setParseNote] = useState(null)
  const fileInputRef = useRef(null)

  const [form, setForm] = useState({
    reason_for_referral: '',
    clinical_summary: '',
    referring_doctor_name: '',
    requirements: [],
  })

  const [lat, setLat] = useState('28.6200')
  const [lon, setLon] = useState('77.2100')

  const [referral, setReferral] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      setImagePreview(dataUrl)
      setImageBase64(dataUrl.split(',')[1])
    }
    reader.readAsDataURL(file)
  }

  async function handleParse() {
    setParsing(true)
    setParseError(null)
    setParseNote(null)
    try {
      const result = await api.parseReferralDocument({ image_base64: imageBase64, extra_text: extraText })
      if (!result.ok) {
        setParseError(result.error || 'Could not read this document — please enter the details manually below.')
        setMode('manual')
        return
      }
      setForm({
        reason_for_referral: result.reason_for_referral || '',
        clinical_summary: result.clinical_summary || '',
        referring_doctor_name: result.referring_doctor_name || '',
        requirements: (result.requirements || []).map((r) => r.requirement_type),
      })
      setParseNote('Extracted from the document — please review and correct anything before submitting.')
      setMode('manual')
    } catch (err) {
      setParseError('Document parsing failed — please enter the details manually below.')
      setMode('manual')
    } finally {
      setParsing(false)
    }
  }

  function toggleRequirement(r) {
    setForm((prev) => ({
      ...prev,
      requirements: prev.requirements.includes(r) ? prev.requirements.filter((x) => x !== r) : [...prev.requirements, r],
    }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const result = await api.createReferral({
        patient_id: patientId,
        journey_id: journeyId || undefined,
        referring_doctor_name: form.referring_doctor_name || undefined,
        origin_lat: Number(lat),
        origin_lon: Number(lon),
        reason_for_referral: form.reason_for_referral,
        clinical_summary: form.clinical_summary,
        requirements: form.requirements.map((r) => ({ requirement_type: r, mandatory: true })),
        source_document_note: imageBase64 ? 'Extracted from a scanned referral letter' : undefined,
      })
      const full = await api.getReferral(result.referral_id)
      setReferral(full)
    } catch (err) {
      setError(err?.response?.data?.error || 'Could not submit referral')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!referral) return
    const interval = setInterval(async () => {
      const r = await api.getReferral(referral.id)
      setReferral(r)
    }, 4000)
    return () => clearInterval(interval)
  }, [referral])

  if (!patientId) {
    return <div className="panel">No demo patient selected yet — go to Patient Home first.</div>
  }

  return (
    <div>
      <h2>Get a Referral</h2>
      <p className="subtitle">
        Bring your own referral — scan a doctor's letter or enter the details yourself, then we search
        for a hospital that can take your case (requirement: referrals are patient-initiated, not
        created by hospital staff).
      </p>

      {!referral && (
        <>
          <div className="tab-row">
            <button className={mode === 'scan' ? 'active' : ''} onClick={() => setMode('scan')}>Scan document</button>
            <button className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>Enter manually</button>
          </div>

          {mode === 'scan' && (
            <div className="panel">
              <h3>Scan doctor's referral letter</h3>
              {parseError && <div className="error-banner">{parseError}</div>}
              <div className="scan-dropzone" onClick={() => fileInputRef.current?.click()}>
                {imagePreview ? (
                  <img src={imagePreview} alt="Referral letter preview" className="scan-preview" />
                ) : (
                  <p>Click to upload a photo of the referral letter (JPEG/PNG)</p>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
              <label>Or paste any typed text from the letter (optional, improves accuracy)</label>
              <textarea value={extraText} onChange={(e) => setExtraText(e.target.value)} />
              <p className="footnote">
                Extraction is best-effort (MedGemma) — you'll review and can correct every field before
                anything is submitted.
              </p>
              <div style={{ marginTop: 16 }}>
                <button disabled={parsing || (!imageBase64 && !extraText.trim())} onClick={handleParse}>
                  {parsing ? 'Reading document…' : 'Extract details'}
                </button>
              </div>
            </div>
          )}

          {mode === 'manual' && (
            <form className="panel" onSubmit={handleSubmit}>
              <h3>Referral details</h3>
              {parseNote && <div className="warning-banner">{parseNote}</div>}
              {error && <div className="error-banner">{error}</div>}
              <label>Reason for referral</label>
              <input value={form.reason_for_referral} onChange={(e) => setForm({ ...form, reason_for_referral: e.target.value })} required />
              <label>Clinical summary</label>
              <textarea value={form.clinical_summary} onChange={(e) => setForm({ ...form, clinical_summary: e.target.value })} required />
              <label>Referring doctor's name (optional)</label>
              <input value={form.referring_doctor_name} onChange={(e) => setForm({ ...form, referring_doctor_name: e.target.value })} />
              <label>Required capabilities (mandatory AND)</label>
              {REQUIREMENT_OPTIONS.map((r) => (
                <div className="checkbox-row" key={r}>
                  <input type="checkbox" id={`req-${r}`} checked={form.requirements.includes(r)} onChange={() => toggleRequirement(r)} />
                  <label htmlFor={`req-${r}`} style={{ margin: 0 }}>{r}</label>
                </div>
              ))}
              <div className="grid-2">
                <div>
                  <label>Your current latitude</label>
                  <input value={lat} onChange={(e) => setLat(e.target.value)} />
                </div>
                <div>
                  <label>Your current longitude</label>
                  <input value={lon} onChange={(e) => setLon(e.target.value)} />
                </div>
              </div>
              <div style={{ marginTop: 16 }}>
                <button type="submit" disabled={busy || form.requirements.length === 0}>
                  {busy ? 'Searching…' : 'Search for a hospital'}
                </button>
              </div>
            </form>
          )}
        </>
      )}

      {referral && (
        <>
          <div className="panel">
            <h3>Referral <span className="mono">{referral.id}</span></h3>
            <p>Status: <span className="badge neutral">{referral.status}</span></p>
            {referral.status === 'NO_VERIFIED_FEASIBLE_DESTINATION' && (
              <div className="error-banner">No hospital currently satisfies every mandatory requirement.</div>
            )}
          </div>

          <div className="panel">
            <h3>Ranked hospitals</h3>
            {referral.evaluations?.filter((e) => e.eligible).length === 0 && (
              <p className="footnote">No eligible hospitals yet.</p>
            )}
            {referral.evaluations
              ?.filter((e) => e.eligible)
              .sort((a, b) => (b.score_optional || 0) - (a.score_optional || 0))
              .map((e, i) => (
                <div className="list-row" key={e.id}>
                  <span>#{i + 1} <span className="mono">{e.hospital_id.slice(0, 8)}</span></span>
                  <span className="mono">score {e.score_optional?.toFixed(3)}</span>
                </div>
              ))}
          </div>

          <div className="panel">
            <h3>Hospital responses</h3>
            {referral.responses.map((r) => (
              <div className="list-row" key={r.id}>
                <span>{r.hospital_name}</span>
                <span className={`badge ${r.status === 'ACCEPTED' ? 'good' : r.status === 'DECLINED' ? 'bad' : 'pending'}`}>{r.status}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
