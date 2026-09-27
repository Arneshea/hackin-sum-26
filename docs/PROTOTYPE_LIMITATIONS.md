# Prototype Limitations & Prototype-vs-Production Boundary

This build pass implements the **end-to-end demo path** described in
`BUILD_SPEC_revised.md` section 45 (Definition of Done) and the core
demo scenario in section 28, with real service-integration code
(Supabase SQL, Hugging Face client, OSRM client) rather than mocked
stand-ins — but it has **not been run against live Supabase / HF /
OSRM credentials in this environment**. You will need to:

1. Create a Supabase project and run the migrations in
   `database/migrations/` in order, then `database/seed/demo_seed.sql`.
2. Obtain a Hugging Face API token with access granted to
   `google/medgemma-4b-it` (it's a **gated** model — you must accept
   Google's license on the model page with the same account) if using
   the hosted Inference API, or ensure the backend host has enough
   memory/disk to load it locally (it's a 4B-parameter multimodal
   model — expect several GB of download and meaningful RAM/VRAM use).
3. Point `OSRM_BASE_URL` at a real OSRM instance (the public
   `router.project-osrm.org` demo server is rate-limited and not
   appropriate for anything beyond light testing).
4. Fill in `backend/.env` and `frontend/.env` from the `.env.example`
   files in each directory.

## What this build pass does NOT implement (explicitly stubbed)

Per the user's stated priority — "end-to-end demo path only, other
edge cases stubbed" — the following are **not** implemented in this
pass, even though the spec describes them:

- **Authentication (Phase 10 / section 19).** There is no Supabase
  Auth wiring yet. The frontend's `HospitalPicker` component is an
  explicit, visible stand-in for "log in as hospital staff at hospital
  X" — see its code comment. RLS policies in
  `003_rls_policies.sql` assume `auth.uid()` / `app_users` are
  populated, so they are **inert until auth is wired up**; all
  backend routes currently use the Supabase service-role connection,
  which bypasses RLS entirely (section 41 notes this is fine for a
  prototype build order but must be closed before any real
  deployment).
- **Recommendation stability / anti-oscillation (step 6.8).** Not
  implemented; the spec itself says only implement this if the demo
  exposes actual ranking flips.
- **Realtime-driven automatic re-evaluation of *all* active referrals
  on every hospital_state change (step 8.2/8.3).** The frontend
  subscribes to Realtime for live updates to *already-open* screens,
  but the backend does not yet proactively recompute every open
  referral when state changes — re-evaluation currently happens when
  a referral is (re)created or after an all-decline event. Wiring a
  Postgres trigger or a backend listener to recompute affected
  referrals automatically is the natural next increment.
- **Concurrency test harness (step 22.3) and reconnection test harness
  (step 22.5).** The atomic SQL functions that make these tests
  meaningful are implemented and unit-testable at the state-machine
  level (`backend/tests/`), but a scripted two-client race test and a
  scripted network-partition test are not included.
- **ABHA/ABDM/FHIR/HFR integration.** Only the reserved
  `external_registry_id_optional` / `abha_id_optional` columns exist,
  per section 24's stated production direction — no real integration
  code.
- **Transport/ambulance fleet tracking.** `transfers.status` models
  the workflow states only; there is no live vehicle-location feed.
  The emergency-dispatch feature (below) similarly does not track a
  real ambulance's live position — it records that a dispatch decision
  was made and to which hospital, nothing more.

## Emergency dispatch button (new requirement)

A red, always-visible "Emergency — Dispatch Ambulance" button on every
patient screen (`frontend/src/components/EmergencyButton.jsx`). One
tap:

1. Reads the browser's geolocation (falls back to a fixed demo
   coordinate if geolocation is denied/unavailable — real deployment
   should require a reliable location source and refuse to proceed
   without one).
2. Calls `POST /emergency-dispatch` with no other input — no symptom
   text, no triage, no confirmation dialog.
3. The backend finds the nearest hospital with `EMERGENCY` capability
   within `candidate_search_radius_km` and immediately advances the
   patient's journey to `EN_ROUTE_TO_HOSPITAL_1`. There is no
   broadcast/accept/decline/select negotiation — see
   `docs/DECISIONS.md` for why this is a deliberately separate, simpler
   code path from Stage-1 matching.

**This is a prototype feature using a synthetic hospital network.** It
does not call a real ambulance service and must not be presented as
one. The UI shows a fixed disclaimer ("does not replace calling your
local emergency number") in the response, but this is not a substitute
for genuine emergency-dispatch infrastructure, which would need
integration with an actual ambulance/EMS provider, verified real-time
vehicle tracking, and a non-web-based fallback channel (SMS/USSD/IVR)
for when the network or device is unreliable — none of which exist
here.

## Patient-initiated referrals + document scanning (changed requirement)

Referrals are now created by the patient/attendant, not by hospital
staff (`frontend/src/pages/patient/PatientReferral.jsx`,
`backend/app/routes/referrals.py`). Two paths:

- **Scan a document**: photograph a doctor's referral letter, MedGemma
  (multimodal) extracts `reason_for_referral`, `clinical_summary`,
  `referring_doctor_name`, and a best-guess requirement checklist as
  JSON. This is explicitly best-effort and is always shown back to the
  patient for review/editing before submission — the extraction
  endpoint (`POST /referrals/parse-document`) never creates a referral
  by itself.
- **Manual entry**: the same form, filled in by hand.

Not implemented in this pass: persisting the actual scanned image
(only a note that a document was used is stored, not the image
itself), any OCR confidence scoring, and any check that the extracted
requirements actually match what a licensed clinician would have
specified — this is a UI convenience over the same referral engine,
not a clinical decision system.

## Prototype-vs-Production boundary (section 24, mirrored here)

| Component | Prototype (this repo) | Production direction |
|---|---|---|
| Stage-1 triage | Hugging Face `google/medgemma-4b-it` (pinned name+revision) | Clinically validated / institutionally approved model |
| Patient identity | Demo identity, optional ABHA field | ABHA/ABDM integration |
| Hospital registry | Synthetic dataset (`is_synthetic = true`) | HFR + institutional registry |
| Hospital state | `/simulator/hospital-state` calling the same DB contract a real adapter would | Hospital HIS/API adapters |
| Realtime | Supabase Realtime (Postgres Changes) | Higher-scale event architecture if required |
| Database | Supabase PostgreSQL | HA/production-grade infrastructure |
| Routing | OSRM + OSM, with a documented geographic-distance fallback | Production routing/traffic service |
| Ranking | Deterministic weighted rules (`ranking_weights_v1`) | Validated optimization/prediction model |
| Wait time | Not implemented | Historical predictive model if justified |
| Reservation | Coordination acknowledgement only (`referral_responses.status = ACCEPTED`) | Integration with authoritative resource system |
| Interoperability | Internal canonical model | FHIR/ABDM-compatible integration |
| Authentication | Not yet wired (see above) | Institutional IAM |
| Authorization | PostgreSQL RLS defined but inert until auth exists | Enterprise policy/IAM |
| Audit | PostgreSQL `audit_events` table | Compliance-grade audit |
| Transport | Simulated status only | Transport/ambulance integration |
| Handoff | Structured prototype record (`handoffs` table) | FHIR/ABDM clinical exchange |

## A note on the Stage-1 triage model

`google/medgemma-4b-it` is a **generative, multimodal** model, not a
fixed-label classifier — see `backend/app/triage/model.py`'s
docstring for exactly how a triage label is obtained (strict-prompt +
parse, never a fabricated confidence score) and
`backend/app/triage/document_parser.py` for how the same loaded model
is reused to read scanned referral letters. Its output (`URGENT` /
`CONSULT_GP` / `SELF_MONITOR`, or `ASSESSMENT_UNAVAILABLE` on failure)
is never used to infer a specialty or resource requirement — see
`backend/app/triage/policy.py`. Structured requirements (ICU,
NEUROLOGY, CT, etc.) come only from an explicit "presenting concern"
checklist the patient/attendant selects themselves (or reviews/edits
after document extraction). Do not change this without re-reading
section 0.5 / step 4.4's "Important limitation".
