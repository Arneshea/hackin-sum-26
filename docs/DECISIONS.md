# DECISIONS.md

A running log of judgment calls made while building this pass, so a
reviewer or future agent can see where the spec left room for a
choice and what was chosen.

## Ranking factor set: section 6.5 vs section 41W

The spec's section 6.5 lists five candidate ranking factors including
"documented operational load if included"; a later section (41W,
"Final MVP Set") gives a slightly different final list. Section 0
states section 0 takes precedence over "older generalized examples
elsewhere," but 41W is not part of section 0 either — it reads as the
project's own later refinement. This build follows 41W's set (travel
time, resource headroom, specialist availability, state freshness)
and folds "operational load" into resource headroom rather than
scoring it twice, per the reasoning in `DATA_MODEL.md`. If your team's
actual intent was to keep operational load as a fifth independent
factor with its own definition, adjust `ranking_weights_v1` and
`ranking.py` accordingly — the weights table is versioned config
specifically so this is a config change, not a code change.

## Stage-1 candidate ordering: no full ranking engine

Step 4.15 only asks Stage-1 to order visible hospitals "using travel
estimate plus currently known operational/capability information" —
it does not ask for the scored, versioned, explainable ranking engine
that section 6 builds for Stage-2. This build keeps Stage-1 simple
(candidate = nearby + capability match, ordered by travel time,
broadcast to top-N) and reserves the full `referral_engine/` module
for Stage-2, per section 6's own framing ("This is the core CS/
decision-support component").

## Hospital-staff auth stand-in

Section 9's build order explicitly says auth is Phase 10, "add after
the core workflow is functional." Rather than block the entire Stage-1/
Stage-2/transfer/handoff flow on wiring up Supabase Auth, this pass
uses a visible, clearly-labeled `HospitalPicker` dropdown as a stand-in
for "which hospital's staff view am I looking at" (see its code
comment). RLS policies are still written and migrated (`003_rls_policies.sql`)
so the schema is ready for auth, but they are inert until `app_users`
rows and real Supabase Auth sessions exist — see
`docs/PROTOTYPE_LIMITATIONS.md`.

## Transfer progression ownership

The spec's transfer state machine (`ACCEPTED -> TRANSFER_INITIATED ->
EN_ROUTE -> PATIENT_RECEIVED -> HANDOFF_COMPLETED`) doesn't explicitly
assign which side (referring vs. receiving hospital) triggers each
step. This build has the *referring* hospital (Hospital 1) trigger
`/transfers/<id>/start` (they're the one dispatching the patient) and
the *receiving* hospital trigger `/transfers/<id>/received` and
`/handoffs/<id>/complete` (they're the one taking custody). `start`
collapses `TRANSFER_INITIATED` and `EN_ROUTE` into one call since this
prototype doesn't model ambulance dispatch as a separately tracked
event.

## Emergency dispatch is a separate, simpler code path

The emergency button (new requirement) deliberately does **not**
reuse the Stage-1 `patient_requests` negotiation (broadcast → hospital
accepts → patient selects → hospital confirms). That flow assumes the
patient can wait through a round of back-and-forth. A red emergency
button implies the opposite: dispatch now, no questions. So
`POST /emergency-dispatch` (`backend/app/routes/emergency.py`) is a
short, linear path: find the nearest hospital with `EMERGENCY`
capability within the search radius, and immediately move the journey
to `EN_ROUTE_TO_HOSPITAL_1` — no broadcast, no accept/decline, no
patient selection. A new `emergency_dispatches` table records what
happened for audit purposes, but it does not participate in the
Stage-1 state machine at all. If nothing is found nearby, the response
says so immediately and tells the person to call local emergency
services directly — it does not silently retry or queue.

## Referral initiation moved from hospital to patient

Originally, a Hospital-1 clinician created the Stage-2 referral once a
patient was UNDER_CARE. The product decision is now that the
**patient/attendant** brings their own referral — scanned or manually
entered — and can do this even without ever having gone through
Stage-1 at all (e.g. they already have a referral letter from an
outside clinic). This required:

- `referrals.referring_hospital_id` became nullable, and a new
  `initiated_by` column (`'PATIENT'` | `'HOSPITAL'`, default
  `'PATIENT'`) plus `referring_doctor_name`, `origin_lat`/`origin_lon`,
  and `source_document_note` columns were added directly to the
  `referrals` table (rather than a separate table) since these are
  simple 1:1 attributes of a single referral, not a repeating
  structure.
- The journey state machine gained a direct `AT_HOME ->
  REFERRAL_INITIATED` transition, for the common case where a patient
  starts a referral without a prior Stage-1 hospital visit in this
  system at all.
- `POST /referrals` now takes `patient_id` + `origin_lat/origin_lon`
  directly (the patient's current location) instead of deriving origin
  from a referring hospital's coordinates. `journey_id` is optional —
  pass it only if there's an existing UNDER_CARE journey to attach to.
- The hospital dashboard lost its "Create Referral" screen entirely;
  hospitals now only *respond* to referrals (accept/decline/transfer/
  handoff), which is also why `Hospital1Dashboard` and
  `ReceivingDashboard` were merged into one `HospitalDashboard` — a
  real hospital plays both the "used to refer out" and "receives
  referrals" role, and there's no longer a UI reason to separate them.

## MedGemma is generative, not a classifier — this changes triage AND enables document parsing

Switching from a text-classification model to `google/medgemma-4b-it`
(a multimodal, instruction-tuned generative model) meant rewriting
`app/triage/model.py`'s inference contract: there are no native class
scores to report, so `model_scores_optional` is always `None` for this
model, and the "label" is obtained by prompting the model to answer
with exactly one fixed token and parsing that token out of its
response — an unparseable response is treated as
`ASSESSMENT_UNAVAILABLE`, the same fallback behavior as before, never
a fabricated guess.

Because MedGemma is multimodal, the same loaded model is reused (never
loaded twice) by `app/triage/document_parser.py` for the new
scanned-referral-letter feature — asking it to extract structured
fields as JSON from a photographed letter. This is explicitly
best-effort: the frontend always shows every extracted field back to
the patient/attendant for review and editing before a referral is
ever submitted (see that module's docstring) — a misread field here
must never silently become a submitted referral for a critical case.

MedGemma is a **gated** model on Hugging Face — using it requires
accepting Google's license on the model page with the account tied to
`HF_API_TOKEN`, or loading will fail with a 401/403. See
`docs/PROTOTYPE_LIMITATIONS.md`.

## Landing page and role-scoped navigation

The single always-visible sidebar (patient + hospital + admin nav
items all shown at once) was replaced with a landing page
(`pages/Landing.jsx`) that picks one of three roles, then a
role-specific layout (`layouts/PatientLayout.jsx`,
`HospitalLayout.jsx`, `AdminLayout.jsx`) that only shows that role's
nav items via nested React Router routes. This is a UI reorganization
only — it does not change any backend contract.

## Geographic-distance routing fallback

Step 4.14 says: "If routing is unavailable, do not fabricate an ETA...
choose one [fallback policy] and document it in configuration." This
build defaults `routing_fallback_policy` to `GEOGRAPHIC_DISTANCE`
(haversine distance / an assumed 30 km/h average speed), clearly
tagged `source: "GEOGRAPHIC_FALLBACK"` in every API response and UI
label, so it's never confused with a real routed ETA. Set the config
value to anything else to instead surface `TRAVEL_TIME_UNAVAILABLE`.

## What "atomic" means in this codebase

Every place the spec calls out a race condition (Stage-1 selection/
confirmation, Stage-2 acceptance) is implemented as a single
conditional `UPDATE ... WHERE status = 'X'` inside a Postgres function
(`002_atomic_transitions.sql`), checked via `ROW_COUNT`, and called
from Flask as one round-trip. No read-then-write race protection lives
in Python or React, per step 7.3's explicit instruction.
