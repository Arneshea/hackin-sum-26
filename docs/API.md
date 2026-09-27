# API.md

Base URL: `http://localhost:8000` (dev). All bodies/responses are
JSON. Every endpoint that mutates state uses the atomic DB functions
described in `STATE_MACHINES.md` where a race is possible.

## Health

- `GET /health` → `{"status": "ok"}` — process is running.
- `GET /ready` → `{"ready": bool, "checks": {...}}`, HTTP 503 if not
  ready. Never reports ready if the DB or triage model isn't usable
  (section 28A).

## Hospitals

- `GET /hospitals` → list of `{id, name, address, latitude, longitude, type, is_synthetic}`
- `GET /hospitals/<id>` → hospital + `capabilities: []`
- `GET /hospitals/<id>/state` → array of `{resource_type, measurement_type, status, available_count_optional, total_count_optional, updated_at, freshness, version}`
- `GET /hospitals/<id>/journeys` → journeys where this hospital is stage1 or stage2
- `GET /hospitals/<id>/patient-request-responses` → this hospital's Stage-1 broadcast rows
- `GET /hospitals/<id>/referral-responses` → this hospital's Stage-2 broadcast rows

## Patients / assessments

- `POST /patients` `{display_name, age?, sex?, abha_id_optional?}` → `{id, created_at}`
- `GET /patients/<id>`
- `POST /assessments` `{patient_id, raw_input, presenting_concerns: [string], requester_role_optional?}`
  → `{assessment_id, triage_label, model_name, model_version, model_scores, care_pathway, requirements, policy_version}`
  (`model_scores` is always `null` for the current MedGemma-based triage model — it's generative, not a
  classifier with class scores; see `docs/DECISIONS.md`.)

## Emergency dispatch (new — no auth/negotiation, immediate)

- `POST /emergency-dispatch` `{patient_id?, location_lat, location_lon}`
  → `{status: "DISPATCHED"|"NO_HOSPITAL_FOUND", dispatch_id, journey_id, hospital?, eta_seconds?, eta_source?, warning}`
  `patient_id` is optional — an anonymous patient record is auto-created if omitted. No triage
  questions, no hospital accept/decline step; the nearest hospital with `EMERGENCY` capability is
  selected immediately and the journey moves straight to `EN_ROUTE_TO_HOSPITAL_1`.

## Stage-1 (patient <-> hospital match)

- `POST /patient-requests` `{patient_id, location_lat, location_lon, urgency, symptom_summary, requirements: [...]}`
  → `{request_id, journey_id, status, broadcast_hospitals: [...]}`
- `GET /patient-requests/<id>` → full request + `responses: [...]`
- `POST /patient-request-responses/<id>/accept`
- `POST /patient-request-responses/<id>/decline` `{reason?}`
- `POST /patient-requests/<id>/select` `{hospital_id}` — atomic (step 4.12)
- `POST /patient-request-responses/<id>/confirm` `{still_eligible: bool}` — atomic
- `POST /patient-requests/<id>/cancel`

## Journeys

- `GET /journeys/<id>` → journey + `stage1_hospital`, `stage2_hospital`, `transfer`
- `POST /journeys/<id>/mark-en-route`
- `POST /journeys/<id>/mark-arrived`
- `POST /journeys/<id>/mark-under-care`

## Stage-2 (referral engine) — patient-initiated

- `POST /referrals/parse-document` `{image_base64?, extra_text?}` → best-effort extraction only, never
  creates a referral: `{ok: bool, reason_for_referral?, clinical_summary?, referring_doctor_name?, requirements?, error?}`
- `POST /referrals` `{patient_id, origin_lat, origin_lon, reason_for_referral, clinical_summary, requirements: [...], journey_id?, referring_doctor_name?, referring_hospital_id?, urgency?, source_document_note?}`
  → evaluates + broadcasts in one call; returns `{referral_id, status, eligible: [...], rejected: [...], policy_version}`.
  `journey_id` is optional — omit it to start a fresh self-referral without a prior Stage-1 visit.
- `GET /referrals/<id>` → referral + `requirements`, `responses`, `evaluations`
- `GET /patients/<id>/referrals` → a patient's own referral history
- `POST /referrals/<id>/accept` `{hospital_id}` — atomic (step 7.3); 409 if another hospital already won
- `POST /referrals/<id>/decline` `{hospital_id, reason}` — re-evaluates and re-broadcasts automatically once every response is decided

## Transfers / handoffs

- `POST /transfers/<id>/start` — ACCEPTED → EN_ROUTE
- `POST /transfers/<id>/received` — EN_ROUTE → PATIENT_RECEIVED
- `POST /handoffs/<id>/complete` `{clinical_summary, current_condition, required_specialty?, required_resources?, relevant_investigations?, referring_doctor, completed_by?}`

## Demo/admin simulator (section 41V)

Requires header `X-Demo-Admin-Token: <DEMO_ADMIN_TOKEN>`.

- `POST /simulator/hospital-state` `{hospital_id, resource_type, measurement_type, status, available_count_optional?, total_count_optional?, source_event_id?}`
  → `{applied: bool, new_version: int}`
- `GET /simulator/network-overview` → every hospital's current state, for the admin dashboard

## Known error shapes

All errors return `{"error": "SOME_CODE", "detail"?: "..."}` with an
appropriate HTTP status (400 bad request, 403 unauthorized, 404 not
found, 409 conflict/race-lost, 503 not ready). Idempotent endpoints
(`/simulator/hospital-state`, referral acceptance) are safe to retry.
