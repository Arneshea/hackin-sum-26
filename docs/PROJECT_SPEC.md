# National Patient Navigation & Referral Coordination Network

## Prototype Engineering Specification & Build Plan

> **Purpose:** This document is the working engineering specification for the SIH prototype. It is written to be given to an AI coding agent such as Antigravity and also used by the team as the implementation contract.
>
> **Important:** The prototype must be honest about what is simulated, what is implemented, and what is only a production integration target.

---
# 0. Critical Contracts Added After Architecture Review

This section takes precedence over older generalized examples elsewhere in this document. The following points were identified as places where an AI coding agent could otherwise invent behavior. They are therefore explicit implementation contracts.

## 0.1 The prototype contains five related state machines

Do not treat the project as one generic status field. Model these separately:

```text
1. PATIENT JOURNEY
       ↓
2. STAGE-1 PATIENT↔HOSPITAL MATCH
       ↓
3. HOSPITAL OPERATIONAL STATE
       ↓
4. STAGE-2 HOSPITAL↔HOSPITAL REFERRAL
       ↓
5. TRANSFER / HANDOFF
```

They are connected, but their states must not be mixed.

## 0.2 One journey links the complete patient path

Create a `journeys` entity linking the Stage-1 request, Hospital 1, Stage-2 referral, Hospital 2, and transfer. This prevents the application from treating each stage as an unrelated transaction.

A journey should be able to answer:

> Where is this patient in the overall workflow right now?

Recommended fields:

```text
journey_id
patient_id
stage1_request_id
stage1_hospital_id
referral_id
stage2_hospital_id
current_stage
current_status
created_at
updated_at
```

## 0.3 Stage-1 matching is genuinely two-sided

A hospital's initial `ACCEPTED` response does not mean final assignment. The sequence is:

```text
Patient request
      ↓
Hospitals respond
      ↓
Patient selects one accepted hospital
      ↓
Selected hospital revalidates and confirms
      ↓
MATCHED
```

Both the patient's selection and the hospital's final confirmation must be atomic state transitions.

## 0.4 Stage-1 request, response and confirmation have separate lifecycles

Do not overload one `status` field to represent all three. A request can be open while individual hospital responses are accepted/declined, and a selected hospital can still fail confirmation after a fresh state check.

## 0.5 The Stage-1 triage transformer does not infer a specialty by itself

The selected medical-triage transformer is a broad pre-triage classifier. Its output is an urgency/care-pathway signal. It must not be treated as a disease diagnosis or as a direct generator of specialist/resource requirements.

The prototype must explicitly separate:

```text
triage model output
        ↓
care-pathway policy
        ↓
structured requirements actually supported by the input/model
        ↓
hospital matching
```

Do not invent mappings such as `urgent → cardiology` unless the product has a separately defined, justified input/rule for that requirement.

If Stage 1 needs a specialty/resource beyond the triage model's output, obtain it from a structured user selection or another explicitly specified component. Do not silently make a medical inference.

## 0.6 Model confidence is not automatically a clinical confidence

The assessment schema may store raw model scores/confidence **only if the selected model exposes them**, together with model name/version. Never interpret an arbitrary classifier score as calibrated clinical probability.

## 0.7 Hospital state is a timestamped observation, not an absolute truth about the physical hospital

The coordination platform stores the **latest known state reported by an identified source**. It must retain:

```text
source
source_event_id
version
updated_at
```

The prototype source is `SIMULATOR`. A production source could be an authenticated hospital system/adapter.

## 0.8 Recommendation, acceptance and reservation are different concepts

```text
Recommendation
= system says hospital currently appears feasible/preferred

Acceptance
= receiving hospital acknowledges willingness to coordinate receipt

Reservation
= authoritative hospital system actually reserves a physical resource
```

The prototype implements the first two. It does not implement the third.

## 0.9 All important decisions must be reproducible

A ranking decision must preserve enough information to answer:

> Why was Hospital A ranked above Hospital B at that moment?

The system should record the ranking policy version, relevant hospital-state versions/timestamps, routing values and candidate eligibility/rejection reasons for important Stage-2 evaluations.

## 0.10 Prototype assumptions must be explicit

The following are configurable prototype assumptions, not medical standards:

- candidate search radius
- request/response timeouts
- stale-data thresholds
- ranking weights
- ranking tie-breakers
- fallback behavior when routing is unavailable

Store them in configuration, not scattered through source code.

---

# 1. Project Definition

## 1.1 Working project name

**National Patient Navigation & Referral Coordination Network**

## 1.2 Core idea

The system connects two related workflows:

### Stage 1 — Patient navigation and first-hospital matching

A patient at home provides symptoms/situation and location. The system performs AI-assisted pre-triage, identifies the required type of care/capabilities, finds nearby feasible hospitals, broadcasts the patient request to multiple eligible hospitals, receives hospital responses, and completes a two-sided selection/confirmation process between the patient and a hospital.

The confirmed hospital becomes **Hospital 1**.

### Stage 2 — Inter-hospital referral coordination

After the patient reaches Hospital 1, the hospital provides the necessary initial care/stabilization and a clinician decides that higher-level care is required. Only then does the referral workflow begin.

The system converts the clinician's referral requirements into a machine-readable request, evaluates the current state of candidate hospitals, removes hospitals that cannot satisfy mandatory requirements, ranks feasible hospitals using current operational factors, sends the referral request to candidates, handles acceptance/decline, coordinates transfer, and records receipt/handoff.

---

# 2. Non-Negotiable Clinical Boundary

The system is **not** an autonomous medical decision-maker.

The distinction is:

```text
CLINICAL DECISION
        ↓
      DOCTOR

RESOURCE / REFERRAL COORDINATION
        ↓
      SOFTWARE

FINAL ACCEPTANCE / CARE
        ↓
   CLINICAL TEAM
```

## 2.1 Emergency workflow rule

An emergency patient must not be modeled as:

```text
No bed → automatically refer elsewhere
```

The ground-level workflow obtained by the team indicates that emergency patients are first treated/stabilized locally, and hospitals may create internal capacity when needed. Referral is a separate clinical decision.

Therefore the application flow is:

```text
Emergency patient arrives
        ↓
Initial treatment / stabilization
        ↓
Clinical assessment
        ↓
Referral required?
      ↙          ↘
    NO            YES
    ↓              ↓
Continue       Stage 2 referral
care           coordination
```

Do not implement automatic outbound referral merely because emergency capacity is full.

---

# 3. Prototype Scope

## 3.1 Must be implemented

### Stage 1

- Patient symptom/situation input
- Patient location
- Hugging Face medical-triage transformer inference
- Deterministic policy layer after model output
- Hospital capability matching
- Nearby-hospital candidate generation
- Map view
- Travel-time estimation
- Multi-hospital request broadcast
- Hospital accept/decline responses
- Patient selection among valid accepting hospitals
- Hospital confirmation
- Patient tracking to Hospital 1

### Stage 2

- Hospital 1 dashboard
- Patient arrival/state
- Doctor-controlled referral creation
- Structured referral requirements
- Current hospital-state lookup
- Hard-constraint feasibility filtering
- Dynamic multi-factor ranking
- Recommendation explanations
- Referral broadcast to feasible receiving hospitals
- Receiving-hospital accept/decline
- Atomic acceptance handling
- Rerouting after decline/expiry where applicable
- Transfer status
- Patient received state
- Structured handoff
- Audit trail
- Real-time hospital-state updates

### Infrastructure

- React + JavaScript frontend
- Python + Flask backend
- Supabase PostgreSQL
- Supabase Auth
- PostgreSQL Row Level Security (RLS)
- Supabase Realtime
- Leaflet + OpenStreetMap
- OSRM routing
- Hugging Face transformer for Stage 1 triage

---

# 4. Explicitly Out of Prototype Scope

Do **not** implement these unless the core workflow is already stable and there is a compelling reason:

- Real hospital HIS/EHR integrations
- Real ABDM/ABHA production integration
- Full FHIR server
- Real ambulance dispatch/fleet integration
- Predictive future bed availability
- Predictive waiting-time model
- Real national hospital network
- Clinical diagnosis model
- Clinical treatment recommendation
- Blockchain audit trail
- Kafka or another message broker
- Microservices architecture
- Kubernetes
- Redis solely for caching/eventing
- Production-grade enterprise IAM
- Custom training of the medical triage transformer
- Voice assistant
- Computer vision
- Complex NLP beyond the selected triage model

These may be production directions or future work, but must not block the prototype.

---

# 5. Technology Decisions

## Frontend

- React
- JavaScript
- CSS
- Leaflet

## Backend

- Python
- Flask

## Data

- Supabase PostgreSQL

## Authentication / authorization

- Supabase Auth
- PostgreSQL RLS

## Realtime

- Supabase Realtime
- For prototype, Postgres Changes is acceptable at the expected small number of connected clients.

## Stage-1 AI

- Hugging Face Transformers
- Use the selected medical-triage transformer specified by the team.
- One example of the type of model intended is `cristian-untaru/biobert-medical-triage`, which is a medical-triage classifier with broad labels such as `self_monitor`, `consult_gp`, and `urgent`.
- The model must be treated as an academic/prototype pre-triage component, not as a diagnostic or clinically validated decision-maker.

## Routing

- Leaflet for map rendering
- OpenStreetMap for map data
- OSRM for routing and travel-time/distance calculations

## Healthcare interoperability target

- ABHA / ABDM for eventual Indian digital-health integration
- FHIR-compatible internal concepts and future integration
- HFR as a production facility-registry integration target where appropriate

---

# 6. Architectural Principles

## 6.1 Database is the source of truth

PostgreSQL current state is authoritative for the coordination platform.

Supabase Realtime is a **change-notification mechanism**, not the source of truth.

## 6.2 Capability and state are different

A hospital's capabilities are relatively static:

```text
Has ICU
Has Neurology
Has CT
```

Its live state is temporal:

```text
ICU currently available: 2
Neurologist currently available: yes
CT currently operational: yes
```

Never collapse these into one ambiguous concept.

## 6.3 Hard constraints precede ranking

A hospital that cannot meet a mandatory requirement must be removed before ranking.

## 6.4 Recommendation is not reservation

The prototype may recommend a hospital and record acceptance, but must not claim that it has physically reserved a hospital bed inside a real hospital's authoritative system.

## 6.5 Human-in-the-loop

Doctors remain responsible for clinical referral decisions.

The system recommends and coordinates; it does not replace clinical judgment.

## 6.6 Prototype data is synthetic

Hospital operational data must be clearly marked as simulated/prototype data.

Do not fabricate real-time capacity figures for real hospitals.

---

# 7. Overall System Architecture

```text
                         PATIENT
                            │
                            ▼
                 ┌────────────────────┐
                 │     React App      │
                 │ Patient / Hospital │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │      Flask API     │
                 └─────────┬──────────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
         Triage       Referral       Routing
         Service       Engine         Service
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                 ┌────────────────────┐
                 │ Supabase/Postgres  │
                 │                    │
                 │ Patients           │
                 │ Hospitals          │
                 │ Hospital State     │
                 │ Requests           │
                 │ Referrals          │
                 │ Audit Events       │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │ Supabase Realtime  │
                 └─────────┬──────────┘
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
             Hospital A        Hospital B
             Dashboard         Dashboard
```

---

# 8. Repository Structure

Start with one repository.

```text
project/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── hooks/
│   │   └── styles/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── routes/
│   │   ├── services/
│   │   ├── referral_engine/
│   │   ├── triage/
│   │   └── utils/
│   ├── tests/
│   └── requirements.txt
│
├── database/
│   ├── migrations/
│   └── seed/
│
├── docs/
│   ├── PROJECT_SPEC.md
│   ├── DATA_MODEL.md
│   ├── API.md
│   ├── STATE_MACHINES.md
│   ├── DECISIONS.md
│   └── PROTOTYPE_LIMITATIONS.md
│
├── scripts/
│   └── seed_demo_data.py
│
└── README.md
```

Do not introduce additional services unless a concrete requirement forces them.

---

# 9. Build Order

Build strictly in this order.

```text
PHASE 1  Foundation
PHASE 2  Hospital data/state
PHASE 3  Backend API
PHASE 4  Stage 1
PHASE 5  Stage 2
PHASE 6  Realtime
PHASE 7  Transfer/handoff
PHASE 8  Auth/RLS/audit
PHASE 9  Reliability/testing
PHASE 10 Deployment/demo
```

The database/state contract must exist before the application grows around it.

---

# 10. PHASE 1 — Foundation

## Step 1.1 — Create repository

Create the repository and folders exactly as described above.

### Do

- Initialize Git
- Create a clean README
- Create `.gitignore`
- Create `.env.example`

### Do not

- Commit secrets
- Commit real patient information
- Commit Supabase service-role keys
- Add unnecessary infrastructure

---

## Step 1.2 — Create Supabase project

Configure:

- PostgreSQL
- Auth
- Realtime

Frontend environment variables should use only client-safe credentials.

Backend secrets belong only on the backend.

---

## Step 1.3 — Write schema migrations

Do not manually create the final database through an untracked sequence of dashboard clicks.

Create SQL migrations under:

```text
database/migrations/
```

Every schema change must be reproducible.

---

# 11. PHASE 2 — Hospital Data and State

## Step 2.1 — `hospitals`

Store stable facility identity only:

```text
id
name
address
latitude
longitude
type
external_registry_id_optional
created_at
updated_at
```

`external_registry_id_optional` is reserved for future HFR/institutional mapping. Do not fabricate a government registry identifier for a synthetic hospital.

## Step 2.2 — `hospital_capabilities`

Represents relatively stable services/capabilities:

```text
id
hospital_id
capability
```

Examples:

```text
EMERGENCY
ICU
CARDIOLOGY
NEUROLOGY
CT
MRI
VENTILATOR_SUPPORT
```

A capability answers: **Can this hospital provide this type of service?**

It does not answer whether that service/resource is available right now.

## Step 2.3 — `hospital_resources`

Represents the resource definition/inventory against which live state is measured:

```text
id
hospital_id
resource_type
measurement_type
total_count_optional
```

`measurement_type` must be one of the explicitly supported types, for example:

```text
COUNT
BINARY_SERVICE
PERSONNEL_AVAILABILITY
```

Do not apply count semantics to a CT or specialist simply because all resources share a table.

## Step 2.4 — `hospital_state`

Represents the latest known operational observation:

```text
id
hospital_id
resource_type
measurement_type
status
available_count_optional
total_count_optional
updated_at
source
source_event_id
version
```

The meaning of `status` depends on `measurement_type`.

Examples:

```text
ICU / COUNT
    status = AVAILABLE
    available_count = 2
    total_count = 30

CT / BINARY_SERVICE
    status = OPERATIONAL

Neurology / PERSONNEL_AVAILABILITY
    status = AVAILABLE or ON_CALL
```

Do not permit meaningless combinations such as `ICU = ON_CALL`.

## Step 2.5 — `hospital_state_events`

Maintain an append-oriented change record:

```text
event_id
hospital_id
resource_type
event_type
old_value
new_value
event_timestamp
source
source_event_id
version
created_at
```

`source_event_id` is the upstream event identity when available; it is the idempotency key for externally supplied updates.

## Step 2.6 — Current load

Do not use a generic unexplained `72% load` as a medical truth. For the prototype, either:

1. derive a documented operational utilization metric from the specific resources used by the demo, or
2. mark a supplied `operational_load` value explicitly as **simulated**.

If load is used in ranking, its definition must be documented in `docs/DATA_MODEL.md` and its value must not be presented as a clinical score.

## Step 2.7 — State freshness

Every state observation has `updated_at`. Derive a freshness category from configuration:

```text
CURRENT
RECENT
STALE
UNKNOWN
```

Freshness is used both for display and, where relevant, eligibility/ranking. A stale timestamp is not merely cosmetic.

## Step 2.8 — State ordering/idempotency

Incoming updates must not overwrite newer state. The API/database layer must verify a monotonic `version` or equivalent timestamp/event-order rule before applying a state update.

Duplicate `source_event_id` values must be safe to process more than once without changing the result after the first successful application.

## Step 2.9 — State simulator

The simulator is a source adapter for the prototype, not a shortcut into Python variables. It must use the same state-update API/data contract that a future hospital adapter would use:

```text
Simulator
    ↓
Hospital State API
    ↓
PostgreSQL current state
    ↓
State event record
```

Do not allow simulator-only code paths to bypass the database contract.

## Step 2.10 — Production integration boundary

Real hospitals may use different HIS/EHR/bed-management systems. The production architecture should therefore be:

```text
Hospital system
      ↓
Hospital-specific adapter/API
      ↓
Canonical hospital-state model
      ↓
Coordination platform
```

Do not design production as if every hospital directly writes into your central Supabase database.

---
# 12. PHASE 3 — Flask Backend

## Step 3.1 — Create app factory

Use a Flask application factory.

Keep configuration separate from route definitions.

---

## Step 3.2 — Create blueprints

Start with:

```text
health
hospitals
patients
patient_requests
referrals
transfers
```

Don't create 30 blueprints before there is real functionality.

---

## Step 3.3 — Implement first API contract

```text
GET /health
GET /hospitals
GET /hospitals/<id>
GET /hospitals/<id>/state
PATCH /hospitals/<id>/state
```

Test these without React.

---

# 13. PHASE 4 — Stage 1

## Step 4.1 — Patient/requester/identity

The app may be used by a patient **or an attendant acting for the patient**. Do not assume `requester = patient`.

The core records should therefore distinguish:

```text
patient_id
requester_user_id_optional
requester_role_optional
```

The prototype may use synthetic/demo identities. Authentication can be added after workflow functionality, but the domain model must not hard-code the assumption that the person typing is necessarily the patient.

## Step 4.2 — Patient record

Minimum prototype fields:

```text
id
display_name
age
sex
abha_id_optional
created_at
```

Do not persist exact location permanently in the patient profile. Location belongs to the active request/journey.

## Step 4.3 — Assessment

Create:

```text
assessments
```

Suggested:

```text
id
patient_id
raw_input
triage_label
model_name
model_version
model_scores_optional
policy_version
created_at
```

Store raw model scores only if the model exposes them. Do not label them as calibrated medical probabilities.

## Step 4.4 — Stage-1 medical-triage transformer

Run the selected Hugging Face transformer in the backend. Load it once during process startup/warm-up; never reload the transformer for every HTTP request.

Create:

```text
backend/app/triage/model.py
backend/app/triage/service.py
backend/app/triage/policy.py
```

Flow:

```text
Raw symptom text
      ↓
Transformer inference
      ↓
Broad triage/care-pathway signal
      ↓
Application policy
      ↓
Care pathway / supported requirements
```

The exact model must be pinned in configuration and documented with its model card/version.

### Important limitation

The selected medical-triage transformer is a broad pre-triage classifier. Its urgency label must not be treated as a diagnosis or as a direct specialty/resource prediction.

If the Stage-1 experience needs a requirement such as `CARDIOLOGY`, `NEUROLOGY`, `CT`, etc., that requirement must come from an explicitly defined structured input/rule or a separately specified model. Do not invent disease-to-specialty mappings from the urgency label alone.

### Do not

- Let transformer output directly select a hospital.
- Call the transformer a diagnostic system.
- Claim clinical validation.
- Invent confidence thresholds without documenting them.
- Load the model for every request.
- Add a second general-purpose LLM just to make the UI conversational.

## Step 4.5 — Triage model failure

If model inference fails, returns invalid output, or the input cannot be processed:

```text
ASSESSMENT_UNAVAILABLE
```

Do not fabricate an urgency result. The UI should clearly indicate that automated assessment is unavailable and follow the predetermined fallback path.

## Step 4.6 — Stage-1 policy

The policy layer maps supported model outputs to broad application pathways. For the example three-class model family:

```text
urgent
   ↓
emergency-care pathway

consult_gp
   ↓
non-emergency clinical-access pathway

self_monitor
   ↓
non-emergency guidance
```

Do not use these labels to infer a disease, specialist, or resource without a separate explicit rule/input.

## Step 4.7 — Stage-1 care requirements

Create a small explicit care-requirement vocabulary used by the prototype. Separate:

```text
CARE PATHWAY
    ↓
REQUIREMENT(S)
```

Requirement entries should support:

```text
requirement_type
value_optional
operator
mandatory
quantity_optional
```

For MVP, support simple mandatory `AND` requirements. Do not build a general logical expression engine.

## Step 4.8 — Patient location privacy

Exact coordinates may be used internally for routing/candidate generation, but the initial multi-hospital broadcast should expose only the minimum location information required to decide whether the hospital can respond.

Do not show exact patient coordinates to the network/admin dashboard. Exact location should only be disclosed to the selected/confirmed hospital when required by the active workflow and permitted by the prototype consent policy.

## Step 4.9 — Patient journey

Create a `journeys` record when the Stage-1 process begins. This is the parent workflow linking the complete patient path.

Recommended stages/statuses:

```text
AT_HOME
REQUESTING_HOSPITAL
MATCHED_TO_HOSPITAL_1
EN_ROUTE_TO_HOSPITAL_1
ARRIVED_AT_HOSPITAL_1
UNDER_CARE
REFERRAL_INITIATED
TRANSFER_TO_HOSPITAL_2
COMPLETED
```

The journey status must not be inferred solely from the UI. It changes through backend state transitions.

## Step 4.10 — Patient request

Create:

```text
patient_requests
```

Suggested:

```text
id
journey_id
patient_id
requester_user_id_optional
urgency
location_lat
location_lon
symptom_summary
requirements_snapshot
status
created_at
expires_at
selection_expires_at
confirmation_expires_at
selected_hospital_id_optional
matched_hospital_id_optional
version
```

Request states:

```text
DRAFT
SUBMITTED
BROADCASTING
PATIENT_SELECTING
CONFIRMING
MATCHED
NO_MATCH
EXPIRED
CANCELLED
CONFIRMATION_FAILED
```

## Step 4.11 — Stage-1 hospital responses

Create:

```text
patient_request_responses
```

Suggested:

```text
id
request_id
hospital_id
status
response_reason
responded_at
expires_at
state_version_seen
travel_seconds_optional
created_at
updated_at
```

Response states:

```text
PENDING
ACCEPTED
DECLINED
WITHDRAWN
EXPIRED
```

The initial hospital `ACCEPTED` response is not final assignment.

## Step 4.12 — Stage-1 mutual selection/confirmation

The exact lifecycle is:

```text
Patient request
      ↓
Eligible hospitals broadcasted
      ↓
Hospital responses
      ↓
Patient selection among ACCEPTED hospitals
      ↓
Selected hospital revalidates current state
      ↓
Hospital CONFIRMS
      ↓
MATCHED
```

If the selected hospital is no longer eligible, the confirmation must fail safely and the patient returns to the remaining valid accepting hospitals or a new candidate search.

Use a backend/database transition to protect selection and confirmation; do not rely on frontend state alone.

## Step 4.13 — Stage-1 expiry/cancellation

There are separate temporal concepts:

```text
request expiry
hospital response expiry
patient selection expiry
hospital confirmation expiry
```

When a patient cancels or a request expires, all relevant hospital responses must become inactive and relevant clients must be notified.

## Step 4.14 — Candidate generation and routing

Candidate generation:

```text
ALL HOSPITALS
     ↓
nearby candidate filter
     ↓
capability/requirement filter
     ↓
current operational-state filter
     ↓
eligible hospitals
```

The exact search radius is configurable prototype policy.

Use OSRM for travel-time/distance estimation. Keep OSRM behind `backend/app/services/routing.py`.

If routing is unavailable, do not fabricate an ETA. The prototype may use a clearly labeled geographic-distance fallback for ordering, or mark travel time unavailable; choose one and document it in configuration.

## Step 4.15 — Stage-1 acceptance visibility

The patient should see only hospitals that have valid responses. A useful ordering can use travel estimate plus currently known operational/capability information. Do not introduce a generic public “hospital rating” unless a specific defensible source and purpose has been established.

---
# 14. PHASE 5 — Hospital 1 and Stage 2

## Step 5.1 — Arrival boundary

Stage 2 must not begin merely because Stage 1 is `MATCHED`. The journey must progress through:

```text
MATCHED
   ↓
EN_ROUTE_TO_HOSPITAL_1
   ↓
ARRIVED_AT_HOSPITAL_1
   ↓
UNDER_CARE
```

Only a Hospital 1 clinician can create the Stage-2 referral.

## Step 5.2 — Hospital 1 dashboard

Hospital 1 should have:

- arriving patients
- patients currently under care
- patient journey status
- create referral
- active referrals
- incoming referrals where authorized

## Step 5.3 — Clinical transition

UI concept:

```text
Patient arrived
      ↓
Initial care / stabilization
      ↓
Clinical assessment
      ↓
Referral required?
```

The application does not determine this transition automatically.

## Step 5.4 — Referral record

Create:

```text
referrals
referral_requirements
```

Suggested `referrals` fields:

```text
id
journey_id
patient_id
referring_hospital_id
urgency
reason_for_referral
clinical_summary
created_by
created_at
expires_at
status
version
accepted_by_hospital_id_optional
accepted_at_optional
```

Suggested `referral_requirements` fields:

```text
referral_id
requirement_type
value_optional
operator
quantity_optional
mandatory
```

For MVP, support mandatory `AND` requirements.

## Step 5.5 — Referral evidence

The current real-world workflow obtained by the team includes a referral letter as a practical artifact. The prototype should therefore be capable of producing a structured digital referral summary containing the referring doctor/hospital and the clinical/referral information used for coordination.

Do not claim that the prototype replaces a legally required paper referral unless that legal/institutional requirement is separately verified.

## Step 5.6 — Referral request is a coordination request, not a bed reservation

When the system recommends/requests Hospital 2, it is asking:

> Can your hospital currently coordinate receipt of this patient under the stated requirements?

It is not claiming that the prototype has locked an actual bed inside the receiving hospital's authoritative resource-management system.

---
# 15. PHASE 6 — Referral Engine

This is the core CS/decision-support component.

Create:

```text
backend/app/referral_engine/
├── eligibility.py
├── ranking.py
├── freshness.py
├── explanation.py
└── evaluation.py
```

## Step 6.1 — Evaluation input contract

The engine receives a consistent snapshot:

```text
Referral requirements
Candidate hospitals
Hospital capabilities
Hospital current-state observations
Patient location
Routing results
Ranking policy version
Evaluation timestamp
```

The engine must not query arbitrary UI state or make HTTP calls itself.

## Step 6.2 — Eligibility

For every candidate:

```text
mandatory capability present?
mandatory current state satisfies requirement?
fresh enough to trust?
```

Output both:

```text
eligible hospitals
rejected hospitals + explicit reasons
```

Example:

```text
Hospital A → ICU available → eligible
Hospital B → ICU unavailable → rejected
Hospital C → no ICU capability → rejected
Hospital D → ICU state stale/unknown → policy-dependent rejection
```

Do not silently substitute a different resource for a mandatory requirement.

## Step 6.3 — Requirement semantics

MVP supports mandatory AND requirements. Do not implement a generalized boolean/optimization language.

Example:

```text
ICU AND NEUROLOGY AND CT
```

## Step 6.4 — Freshness

Freshness has both a timestamp and a policy meaning:

```text
CURRENT
RECENT
STALE
UNKNOWN
```

Thresholds are prototype configuration, not medical standards.

## Step 6.5 — Ranking factors

For MVP use only factors for which the system actually has data:

```text
1. travel time
2. relevant resource headroom/availability
3. relevant specialist availability
4. documented operational load if included
5. state freshness
```

Do not include generic hospital ratings, predicted waiting time or future bed prediction in the MVP.

If operational load remains in the ranking, its exact definition must be documented; otherwise omit it. Do not use an unexplained percentage.

## Step 6.6 — Ranking normalization

Normalize factors to a common scale before combining them. Store weights in a versioned configuration object.

Every ranking run must record the policy version used.

## Step 6.7 — Deterministic tie-breaking

When scores are equal or materially indistinguishable, use deterministic tie-breakers such as:

```text
1. fresher state
2. shorter travel time
3. stable hospital identifier
```

Do not let database row ordering determine the winner accidentally.

## Step 6.8 — Recommendation stability

Do not replace an active recommendation because of insignificant score oscillations. Use a configurable improvement margin if live recomputation causes frequent ranking flips.

Do not over-engineer this for MVP; implement only if the demo exposes actual oscillation.

## Step 6.9 — Reproducible evaluation

Create an evaluation record for important referral-ranking runs:

```text
id
referral_id
policy_version
evaluated_at
hospital_id
eligible
rejection_reason_optional
score_optional
factors_json
state_versions_json
routing_snapshot_json
```

This allows the system to answer:

> Why was Hospital A ranked above Hospital B at that time?

## Step 6.10 — Explanation

Return human-readable reasons generated from the same factors used by the engine. Example:

```text
Hospital A recommended because:
✓ ICU available
✓ Neurology available
✓ CT operational
✓ 14 min estimated travel
✓ State updated 31 sec ago
```

Do not create explanations that mention factors that were not actually used.

## Step 6.11 — No feasible hospital

If all candidates fail mandatory requirements:

```text
NO_VERIFIED_FEASIBLE_DESTINATION
        ↓
manual coordination / escalation state
```

Never silently fall back to the nearest infeasible hospital.

---
# 16. PHASE 7 — Receiving Hospital Acceptance

## Step 7.1 — Referral broadcast

Create:

```text
referral_responses
```

Suggested:

```text
id
referral_id
hospital_id
status
reason
responded_at
expires_at
```

---

## Step 7.2 — Acceptance

Before accepting:

1. Verify referral is still pending.
2. Re-read current relevant hospital state.
3. Re-check mandatory requirements.
4. Verify the hospital user is authorized for that hospital.
5. Attempt the atomic status transition.

Only then mark accepted.

Acceptance must be idempotent: retrying the same successful action must not create a second acceptance or a second transfer.

---

## Step 7.3 — Atomic acceptance

Use a database-level conditional transition.

Concept:

```sql
UPDATE referrals
SET status = 'ACCEPTED',
    accepted_by_hospital_id = :hospital_id,
    accepted_at = NOW()
WHERE id = :referral_id
  AND status = 'PENDING_ACCEPTANCE';
```

If one row changes, that hospital wins.

If zero rows change, another transition already won.

Do not implement this race protection in React.

---

## Step 7.4 — Decline

Decline reason codes:

```text
ICU_UNAVAILABLE
SPECIALIST_UNAVAILABLE
DIAGNOSTIC_UNAVAILABLE
CAPACITY_UNAVAILABLE
OTHER
```

Then recompute remaining candidates as appropriate.

---

# 17. PHASE 8 — Realtime

Do not build realtime before the workflows work correctly with normal API reads.

First prove:

```text
state update → database correct
```

Then add realtime.

---

## Step 8.1 — Subscribe to relevant state

Prototype:

- `hospital_state` for authorized network views
- relevant patient-request response changes
- relevant referral changes
- relevant journey/transfer changes

Do not subscribe every user to every national event. Realtime channels must follow the same authorization boundary as the underlying data.

---

## Step 8.2 — Hospital state event flow

```text
Hospital simulator
      ↓
Flask/API
      ↓
PostgreSQL
      ↓
Realtime notification
      ↓
Relevant clients
      ↓
Referral recomputation when required
```

Database remains authoritative.

---

## Step 8.3 — Recompute only affected referrals

The first implementation may recompute all active relevant referrals after a state change.

Then optimize by identifying which requirements the changed resource affects.

Do not prematurely implement sophisticated event-routing infrastructure.

---

## Step 8.4 — Reconnect behavior

If realtime disconnects:

```text
show stale/live-warning
↓
refresh authoritative state
↓
resubscribe
```

Do not assume every missed event will be replayed into the browser.

---

# 18. PHASE 9 — Transfer and Handoff

## Step 9.1 — Transfer state

```text
ACCEPTED
    ↓
TRANSFER_INITIATED
    ↓
EN_ROUTE
    ↓
PATIENT_RECEIVED
    ↓
HANDOFF_COMPLETED
```

---

## Step 9.2 — Handoff

Create:

```text
handoffs
```

Suggested fields:

```text
id
referral_id
patient_id
clinical_summary
current_condition
required_specialty
required_resources
relevant_investigations
referring_doctor
completed_by
completed_at
```

Do not attempt to make this a complete medical record in the prototype.

---

# 19. PHASE 10 — Authentication and RLS

Add after the core workflow is functional.

## Roles

```text
PATIENT
DOCTOR
HOSPITAL_STAFF
NETWORK_ADMIN
```

## Patient access

Own patient data/requests/referrals only.

## Hospital access

Hospital-specific operational data and authorized referral information.

## Network admin

Demo/network-level access.

Use Supabase Auth for identity and PostgreSQL RLS for row-level access.

---

# 20. PHASE 11 — Audit

Create:

```text
audit_events
```

Suggested:

```text
id
actor_id
actor_role
action
entity_type
entity_id
timestamp
metadata
```

Log major actions:

```text
PATIENT_REQUEST_CREATED
HOSPITAL_ACCEPTED_REQUEST
PATIENT_SELECTED_HOSPITAL
HOSPITAL_CONFIRMED_MATCH

REFERRAL_CREATED
REFERRAL_BROADCAST
REFERRAL_ACCEPTED
REFERRAL_DECLINED

STATE_UPDATED
TRANSFER_STARTED
PATIENT_RECEIVED
HANDOFF_COMPLETED
```

Do not add blockchain to the prototype merely to make the audit sound impressive.

---

# 21. PHASE 12 — Failure Handling

Every subsystem must have an explicit failure path.

## AI failure

```text
MODEL_ERROR / ASSESSMENT_UNAVAILABLE
```

Do not guess.

## Routing failure

```text
TRAVEL_TIME_UNAVAILABLE
```

Use the defined fallback or tell the user that routing information is unavailable.

## Realtime failure

Show a stale/live warning and refresh authoritative state.

## Database failure

Do not display old state as current without indicating it.

## No hospital responds

Move request to an expiry/no-response state.

## All hospitals decline

Move to escalation/manual coordination.

## Receiving hospital becomes unavailable

Revalidate and, if necessary, rerun coordination.

## Patient cancels

Terminate the request/transfer according to its current state.

---

# 22. PHASE 13 — Testing

## 22.1 Unit tests

Test the referral engine:

```text
ICU unavailable → rejected
specialist unavailable → rejected
all mandatory requirements available → eligible
stale data → freshness effect applied
no feasible hospitals → escalation state
```

## 22.2 State-machine tests

Try legal and illegal transitions.

Examples:

```text
PENDING → ACCEPTED       valid
PENDING → DECLINED       valid
ACCEPTED → TRANSFER      valid
TRANSFER → RECEIVED      valid
COMPLETED → ACCEPTED     invalid
```

## 22.3 Concurrency test

Two hospitals attempt to accept the same referral at approximately the same time.

Expected:

```text
exactly one accepted
other rejected/stale
```

## 22.4 Realtime test

Open two or more clients.

Change hospital state.

Verify relevant clients update without refresh.

## 22.5 Reconnection test

Disconnect network temporarily.

Reconnect.

Verify current state is reloaded.

---

# 23. Prototype Data Rules

Use only synthetic/demo patient data.

Use synthetic hospital operational state.

Use fictional or clearly labeled prototype hospital entities if real hospital capacity is not being obtained through a legitimate source.

Do not present seeded values as current real-world hospital capacity.

---

# 24. Prototype-vs-Production Boundary

Maintain this table in the code documentation.

| Component | Prototype | Production direction |
|---|---|---|
| Stage-1 triage | Hugging Face medical-triage model | Clinically validated model / institutional validation |
| Patient identity | Demo identity, optional ABHA field | ABHA/ABDM integration |
| Hospital registry | Synthetic dataset | HFR + institutional registry |
| Hospital state | Simulator | Hospital HIS/API adapters |
| Realtime | Supabase Realtime | Higher-scale event architecture if required |
| Database | Supabase PostgreSQL | HA/production-grade infrastructure |
| Routing | OSRM + OSM | Production routing/traffic service |
| Ranking | Deterministic weighted rules | Validated optimization/prediction |
| Wait time | Not implemented | Historical predictive model if justified |
| Reservation | Coordination acknowledgement | Integration with authoritative resource system |
| Interoperability | Internal canonical model | FHIR/ABDM-compatible integration |
| Authentication | Supabase Auth | Institutional IAM |
| Authorization | PostgreSQL RLS | Enterprise policy/IAM |
| Audit | PostgreSQL audit events | Compliance-grade audit |
| Transport | Simulated status | Transport/ambulance integration |
| Handoff | Structured prototype record | FHIR/ABDM clinical exchange |

---

# 25. Live Hospital State: Prototype vs Real World

## Prototype

```text
Hospital Simulator
      ↓
Hospital State API
      ↓
PostgreSQL
      ↓
Supabase Realtime
      ↓
Referral Engine / Dashboards
```

## Production

```text
Hospital HIS / Bed Management / Clinical Systems
                    ↓
          Hospital-specific adapter
                    ↓
          Canonical operational state
                    ↓
          Coordination platform
                    ↓
             Referral engine
```

Do not design the production system as if every hospital writes directly into your central Supabase database.

---

# 26. Stage-1 Full Flow

```text
PATIENT AT HOME
      ↓
Symptoms / situation input
      ↓
Hugging Face triage transformer
      ↓
Validated urgency category
      ↓
Deterministic patient-care policy
      ↓
Required hospital capabilities
      ↓
Nearby candidate hospitals
      ↓
Capability + operational eligibility
      ↓
Route/time calculation
      ↓
Patient request broadcast
      ↓
┌─────────────┬─────────────┬─────────────┐
│ Hospital A  │ Hospital B  │ Hospital C  │
│ ACCEPT      │ ACCEPT      │ DECLINE     │
└─────────────┴─────────────┴─────────────┘
      ↓
Patient sees valid accepting hospitals
      ↓
Patient selects Hospital A
      ↓
Hospital A confirms
      ↓
MATCHED
      ↓
Patient reaches Hospital 1
```

---

# 27. Stage-2 Full Flow

```text
Hospital 1
      ↓
Initial treatment / stabilization
      ↓
Doctor determines higher-level referral required
      ↓
Structured referral requirements
      ↓
Candidate hospital lookup
      ↓
Hard constraint filter
      ↓
Feasible hospitals
      ↓
Travel + resource + specialist + load + freshness ranking
      ↓
Recommendation + explanation
      ↓
Referral broadcast
      ↓
Receiving hospital revalidates state
      ↓
Atomic acceptance
      ↓
TRANSFER_INITIATED
      ↓
EN_ROUTE
      ↓
PATIENT_RECEIVED
      ↓
HANDOFF_COMPLETED
```

---

# 28. The Core Demo Scenario

This should be the main internal-round demonstration.

## Scenario

Start with:

```text
Hospital A
ICU available = 2

Hospital B
ICU available = 0

Hospital C
ICU available = 1
```

A referral requires ICU.

Initial ranking:

```text
Hospital A #1
Hospital C #2
Hospital B rejected
```

Then use the simulator:

```text
Hospital A ICU
2 → 1
```

Still feasible.

Then:

```text
Hospital A ICU
1 → 0
```

Realtime update propagates.

Hospital A becomes infeasible.

System reranks:

```text
Hospital C #1
Hospital A rejected
Hospital B rejected
```

Then Hospital C accepts the referral.

Transfer is started.

Patient is marked received.

Handoff completed.

This single scenario demonstrates:

- database state
- state transitions
- realtime updates
- hard constraints
- ranking
- explanation
- hospital interaction
- referral lifecycle

---

# 28A. Runtime Readiness Checks

Before deployment, verify explicitly:

```text
Database reachable
Supabase configuration valid
Triage model loaded
Routing service reachable or fallback configured
Realtime configured
```

Expose separate health/readiness behavior if needed:

```text
GET /health   → process is running
GET /ready    → required prototype dependencies are ready
```

Do not make a failed external dependency look healthy.

---

# 29. Deployment

Deploy only after the core workflow works locally.

Target topology:

```text
                INTERNET
                   │
          ┌────────┴────────┐
          ▼                 ▼
      React App         Flask API
          │                 │
          └────────┬────────┘
                   ▼
             Supabase Cloud
       PostgreSQL / Auth / Realtime
```

Configure:

- CORS
- frontend environment variables
- backend environment variables
- Supabase redirect URLs
- RLS policies
- production build
- health endpoint

Test the deployed system independently of localhost.

---

# 30. Demo Client Setup

Use multiple browser profiles/incognito windows or separate sessions:

```text
Window 1 → Patient
Window 2 → Hospital 1
Window 3 → Receiving Hospital
Window 4 → Network/Admin simulator
```

Do not rely on one browser tab with manually changing roles during the core demo.

---

# 31. UI Requirements

## Patient

Primary screens:

```text
Home
Assessment
Hospital Options
Hospital Request Status
Hospital Confirmation
Journey / Referral Tracking
```

## Hospital 1

```text
Dashboard
Patients
Create Referral
Referral Engine Results
Active Transfers
```

## Receiving Hospital

```text
Dashboard
Incoming Requests
Referral Details
Accept / Decline
Patient Received
Handoff
```

## Admin / Demo

```text
Network Overview
Hospital State Simulator
Live Events
Referral Activity
```

Keep the UI visually simple and operational.

Do not add decorative AI/chatbot widgets that do not support the workflow.

---

# 32. Recommended API Surface

Start small.

## Patients

```text
POST /patients
GET /patients/<id>
```

## Assessments

```text
POST /assessments
```

## Hospitals

```text
GET /hospitals
GET /hospitals/<id>
GET /hospitals/<id>/state
PATCH /hospitals/<id>/state
```

## Stage-1 requests

```text
POST /patient-requests
GET /patient-requests/<id>
POST /patient-requests/<id>/select
POST /patient-requests/<id>/cancel
```

## Stage-1 responses

```text
POST /patient-request-responses/<id>/accept
POST /patient-request-responses/<id>/decline
POST /patient-request-responses/<id>/confirm
```

## Stage-2 referrals

```text
POST /referrals
GET /referrals/<id>
POST /referrals/<id>/accept
POST /referrals/<id>/decline
```

## Transfers

```text
POST /transfers/<id>/start
POST /transfers/<id>/received
POST /handoffs/<id>/complete
```

Refine exact JSON schemas before frontend integration.

---

# 33. API Contract Rule

Every endpoint must define:

```text
HTTP method
path
authentication requirement
request JSON
response JSON
success status
known error statuses
idempotency expectations
```

Do not let the frontend guess backend shapes.

Keep API definitions in:

```text
docs/API.md
```

---

# 33A. API Idempotency and Concurrency Rules

Critical write operations must be safe against browser retries and duplicated network requests.

At minimum protect:

```text
create patient request
create referral
patient hospital selection
hospital confirmation
referral acceptance
referral decline
transfer start
patient received
handoff completion
```

For operations where a client may retry, accept an idempotency key or otherwise enforce a database invariant that prevents duplicate state transitions.

The backend, not React, owns state-transition correctness.

---

# 34. Coding Standards for the Prototype

Write code that the team can understand and defend.

Prefer:

- explicit functions
- descriptive names
- small modules
- straightforward SQL
- typed/validated inputs where appropriate
- clear error handling
- comments explaining non-obvious domain logic

Avoid:

- unnecessary abstractions
- generic “AI generated” utility layers
- huge files
- deeply nested conditionals
- unexplained constants
- magic scores
- hidden network calls
- duplicate business logic in frontend and backend

The source should look like a student engineering team deliberately designed the system, not like a framework-generated template.

---

# 35. Testing Checklist Before Calling the Prototype Complete

## Stage 1

- [ ] Patient can enter symptoms.
- [ ] Transformer runs.
- [ ] Transformer failure is handled.
- [ ] Urgency policy runs deterministically.
- [ ] Nearby hospitals are identified.
- [ ] Ineligible hospitals are filtered.
- [ ] Travel times appear.
- [ ] Multiple hospitals receive the request.
- [ ] Hospitals can accept/decline.
- [ ] Patient sees valid accepting hospitals.
- [ ] Patient selects one.
- [ ] Hospital confirms.
- [ ] Selected hospital becomes unavailable before confirmation and the system recovers safely.
- [ ] Patient cancellation deactivates outstanding hospital responses.
- [ ] Hospital withdrawal is handled.
- [ ] Repeated submission cannot create an unintended duplicate active request.
- [ ] Stage 1 closes correctly.

## Stage 2

- [ ] Hospital can view patient.
- [ ] Doctor explicitly creates referral.
- [ ] Requirements are structured.
- [ ] Infeasible hospitals are filtered.
- [ ] Feasible hospitals are ranked.
- [ ] Explanation is shown.
- [ ] Receiving hospital receives request.
- [ ] Receiving hospital revalidates current state.
- [ ] Exactly one acceptance wins.
- [ ] Decline can trigger rerouting.
- [ ] Transfer states work.
- [ ] Patient receipt works.
- [ ] Handoff works.
- [ ] Doctor override is recorded with actor/time/reason if override is exposed.
- [ ] Referral recommendation can be explained from recorded evaluation data.
- [ ] Ranking policy/version used for the recommendation is recorded.
- [ ] Doctor override, if exposed, is recorded with actor/time/reason.
- [ ] Hospital acceptance does not claim physical resource reservation.

## Live state

- [ ] Simulator changes state through API.
- [ ] State is stored in PostgreSQL.
- [ ] Event is recorded.
- [ ] Duplicate state event is idempotent.
- [ ] Older/out-of-order state event cannot overwrite newer state.
- [ ] Realtime reaches relevant clients.
- [ ] Referral ranking responds to relevant changes.
- [ ] Stale data is visible.
- [ ] Reconnect restores current state.

## Security

- [ ] Authentication works.
- [ ] Hospital users cannot modify other hospitals.
- [ ] Patient cannot view other patients.
- [ ] Service-role secrets are server-only.
- [ ] RLS policies are actually tested.

---

# 36. Performance/Scale Decisions

Do not optimize for national scale in the prototype.

The prototype target is a small synthetic network, e.g. 10–20 hospitals.

Measure:

- Stage-1 transformer inference latency
- transformer cold-load time
- Stage-1 warm inference latency
- Stage-1 matching latency
- routing latency
- referral-engine computation time
- realtime propagation time
- acceptance response time
- rerouting time

The triage model must be loaded once per backend process, not once per request.

Do not introduce new infrastructure because a number such as “10–20 hospitals” sounds small; introduce it only after measuring a real bottleneck.

---

# 37. Team Build Order

For a 4-person team, split by subsystem.

## Person 1 — Data/Backend

- Supabase
- schema
- Flask
- APIs
- auth/RLS
- audit

## Person 2 — Stage 1

- patient UI
- Hugging Face transformer
- policy layer
- hospital request workflow

## Person 3 — Hospital state + referral engine

- simulator
- hospital state
- eligibility
- ranking
- explanation

## Person 4 — Stage 2/Realtime/UI

- hospital dashboard
- accept/decline
- realtime subscriptions
- transfer/handoff
- network dashboard

### Mandatory rule

All four people must agree on the database/API/state contracts before implementing independently.

---

# 38. Development Rule: Do Not Move Forward Too Early

After each phase:

1. Run it.
2. Test it.
3. Verify database state.
4. Verify API response.
5. Verify UI behavior.
6. Record any design change.
7. Only then begin the next phase.

Do not build the complete frontend first and “connect the backend later.”

Do not build the AI first and make the rest fit around it.

Do not build a visual simulator that bypasses the real API.

---

# 39. Decision Log

Every important architectural choice should go into:

```text
docs/DECISIONS.md
```

Use:

```text
Decision:
Why:
Alternatives considered:
Why rejected:
Prototype/production:
```

Examples:

```text
Decision: PostgreSQL is the source of truth for current coordination state.
Why: relational entities + transactions + concurrency requirements.
Alternative: NoSQL.
Rejected: relational constraints and transactional workflow are more central here.
Prototype/production: both.
```

and:

```text
Decision: Stage-1 hospitals must accept before the patient can select them.
Why: patient should choose among hospitals that have indicated willingness/capability.
Prototype/production: both, subject to final workflow policy.
```

---

# 39A. Critical Assumptions That Must Remain Visible

The following are prototype assumptions, not external facts or clinical standards:

- Stage-1 hospital-response timeout and selection timeout.
- Candidate radius/search area and any top-N broadcast limit.
- Freshness thresholds.
- Ranking normalization and weights.
- Current-load definition for the prototype.
- Care-requirement mappings from the triage model output.
- Any fallback used when routing is unavailable.
- Any fallback used when realtime is unavailable.

Keep these values in configuration and document their purpose. Do not bury them as unexplained constants.

---

# 40. Production Limitations to State Explicitly

These are not failures of the prototype. They are known integration boundaries.

1. Hospital-state feeds are simulated.
2. Hospital adapters are not integrated with real HIS/EHR systems.
3. ABHA/ABDM integration is not implemented unless legitimate sandbox access is obtained.
4. FHIR compatibility is a production interoperability target, not a full prototype FHIR interface.
5. Bed acceptance is coordination acknowledgement, not authoritative reservation.
6. Travel time is a routing estimate, not guaranteed live-traffic ETA.
7. Triage transformer is not clinically validated.
8. Ranking weights are prototype assumptions.
9. No future bed/wait prediction is claimed.
10. No ambulance dispatch integration is claimed.

Never conceal these limitations if asked.

---

# 41. Important Corrections to Current SIH Material

Before final submission, update claims that currently overstate implementation.

### Change

> First hospital to accept locks the bed instantly.

### To

> First valid hospital acceptance confirms referral coordination.

---

### Change

> Built on ABDM/FHIR APIs.

### To

> Production interoperability target: ABDM/FHIR-compatible APIs.

---

### Remove or revise

> Hospital rating as a ranking factor.

Unless a defensible operational source/definition is established, do not make star rating part of emergency hospital ranking.

---

### Remove from MVP ranking

> Expected waiting time.

There is no validated predictive wait-time model/data in the prototype.

---

# 42. Final System Mental Model

The system is not:

```text
AI → hospital
```

It is:

```text
PATIENT / DOCTOR INPUT
        ↓
STRUCTURED REQUIREMENTS
        ↓
CURRENT HOSPITAL STATE
        ↓
HARD CONSTRAINTS
        ↓
FEASIBLE SET
        ↓
DYNAMIC RANKING
        ↓
EXPLAINABLE RECOMMENDATION
        ↓
HUMAN ACCEPTANCE / SELECTION
        ↓
REALTIME STATEFUL WORKFLOW
        ↓
TRANSFER + HANDOFF
```

The technically strongest component is the **stateful referral coordination system under changing hospital conditions**, not the AI model itself.

---

# 43. Primary Technical References

Use these references for implementation questions and keep the external facts separate from prototype assumptions.

1. Supabase, “Database — PostgreSQL,” Supabase Documentation. https://supabase.com/docs/guides/database/overview
2. Supabase, “Postgres Changes,” Supabase Documentation. https://supabase.com/docs/guides/realtime/postgres-changes
3. Supabase, “Row Level Security,” Supabase Documentation. https://supabase.com/docs/guides/database/postgres/row-level-security
4. Supabase, “Auth,” Supabase Documentation. https://supabase.com/docs/guides/auth
5. PostgreSQL Global Development Group, “Transaction Isolation,” PostgreSQL Documentation. https://www.postgresql.org/docs/current/transaction-iso.html
6. Flask Documentation, “Blueprints.” https://flask.palletsprojects.com/en/stable/blueprints/
7. Hugging Face, “Transformers Pipelines Documentation.” https://huggingface.co/docs/transformers/main_classes/pipelines
8. Hugging Face, `cristian-untaru/biobert-medical-triage` model card. https://huggingface.co/cristian-untaru/biobert-medical-triage
9. OSRM Project, “OSRM HTTP API Documentation.” https://project-osrm.org/docs/
10. Leaflet Documentation, “Leaflet API Reference.” https://leafletjs.com/reference.html
11. HL7 International, “FHIR R4 ServiceRequest.” https://hl7.org/fhir/R4/servicerequest.html
12. HL7 International, “FHIR Workflow Management.” https://www.hl7.org/fhir/R4/workflow-management.html
13. National Health Authority, Government of India, “Health Facility Registry.” https://abdm.gov.in/health-facilities
14. National Health Authority, Government of India, “ABDM.” https://abdm.gov.in/
15. National Informatics Centre, Government of India, “ABHA / Health ID.” https://ors.gov.in/healthid/
16. Ministry of Health and Family Welfare / PIB, Government of India, “Inter-AIIMS Referral Portal,” 2025. https://www.pib.gov.in/PressReleasePage.aspx?PRID=2120252&lang=2&reg=48

---

# 44. Final Implementation Rule

**Do not ask an AI coding agent to “build the whole project” in one prompt.**

Use this document as the system contract and implement one phase at a time.

Each Antigravity task should:

1. Identify the exact subsystem being changed.
2. Read this specification.
3. Inspect existing code before modifying it.
4. Make the smallest coherent change.
5. Run tests/build checks.
6. Report files changed.
7. Report any assumptions.
8. Stop before inventing the next subsystem.

The coding agent must never silently alter the product boundary, state machines, database semantics, or clinical boundaries.

If a requirement is ambiguous, **stop and surface the ambiguity rather than inventing behavior**.

The coding agent must pay particular attention to the pre-coding gates in Section 44A. It must not invent medical mappings, resource semantics, request/confirmation transitions, reservation semantics, privacy behavior, ranking factors, or fallback policies that are not specified.

---

# 41A. Critical Design Clarifications Before Database Implementation

The earlier specification establishes the major architecture, but the following contracts must be made explicit before an AI coding agent is allowed to design the final schema. These are not optional implementation details; they prevent contradictory state and unnecessary rework.

---

## 41A.1 — Patient Journey State Is Separate From Request State

Do not use `patient.status` as the master workflow state.

A patient can exist independently of a request, while multiple requests or referrals may exist over time.

Use a journey-level identifier to correlate the complete prototype journey:

```text
journey_id
    ↓
Stage-1 request
    ↓
Hospital 1 match
    ↓
Hospital 1 arrival
    ↓
Referral
    ↓
Hospital 2 acceptance
    ↓
Transfer
    ↓
Handoff
```

The journey is an application correlation concept. Individual requests, referrals and transfers retain their own state machines.

Do not allow one table to silently represent all of these states.

---

## 41A.2 — Stage-1 Matching State Machine

The Stage-1 two-sided interaction must be represented explicitly.

```text
DRAFT
  ↓
SUBMITTED
  ↓
BROADCASTING
  ↓
RESPONSES_OPEN
  ├── hospitals accept/decline
  ↓
PATIENT_SELECTING
  ↓
HOSPITAL_CONFIRMING
  ├── CONFIRMED → MATCHED
  └── REJECTED  → PATIENT_SELECTING / REMATCH
```

Terminal states:

```text
MATCHED
NO_MATCH
EXPIRED
CANCELLED
```

Important rules:

1. A hospital's initial acceptance is **not** the final Stage-1 match.
2. The patient can select only from currently valid accepting hospitals.
3. The selected hospital must revalidate its relevant state before confirmation.
4. A failed confirmation must return the patient to a valid selection/rematching state rather than silently ending the journey.
5. Patient cancellation must invalidate outstanding hospital responses.

Do not represent `ACCEPTED` and `CONFIRMED` as the same event.

---

## 41A.3 — Stage-1 Response State Machine

Each hospital's response has its own lifecycle:

```text
PENDING
  ├── ACCEPTED
  ├── DECLINED
  ├── EXPIRED
  └── WITHDRAWN
```

`ACCEPTED` means:

> The hospital has indicated willingness/capability to proceed based on the information supplied at that time.

It does **not** mean:

> The patient is assigned.

A hospital may withdraw before final confirmation. The patient UI must immediately stop treating a withdrawn response as selectable.

---

## 41A.4 — Stage-1 Selection Must Be Transactional

When the patient selects Hospital A:

```text
patient selects A
      ↓
backend revalidates A
      ↓
conditional confirmation request
      ↓
A confirms
      ↓
MATCHED
```

The backend must not trust the state displayed in the browser because it may be stale.

If Hospital A can no longer confirm, the selection fails safely and the patient is offered another valid accepting hospital.

The same database-level state-transition principle used for Stage-2 acceptance applies here.

---

# 41B. Stage-1 Clinical Output Contract

The triage transformer and hospital matching system must be separated by an explicit contract.

The transformer is responsible only for the output categories supported by the selected model.

The application then maps that output into **prototype care requirements**.

```text
Raw symptom input
      ↓
Selected Hugging Face triage model
      ↓
Model output
      ↓
Validated triage result
      ↓
Prototype care-requirement mapping
      ↓
Hospital eligibility
```

Do not allow the model to invent arbitrary capabilities such as `ICU`, `CT`, `cardiology`, etc. unless the application policy explicitly defines that mapping.

The mapping must live in:

```text
backend/app/triage/policy.py
```

and be versioned.

For every model output used by the prototype, the policy must define:

```text
triage label
→ patient-facing guidance category
→ whether hospital discovery is offered
→ prototype care capability requirements, if any
```

The mapping is an **application assumption**, not a medically validated clinical rule.

Do not claim that the model itself clinically determines the hospital's required department or resources.

---

## 41B.1 — Model Output and Confidence

Store:

```text
model_name
model_version
raw_label
model_score/confidence, if actually provided by the inference interface
policy_version
```

Do not interpret an uncalibrated model score as a medical probability.

If the selected model/inference implementation does not provide a meaningful confidence value, do not manufacture one.

The UI should not show a percentage unless its meaning is established.

---

## 41B.2 — Assessment and Patient Request Are Separate

An assessment does not automatically create a hospital request.

Correct flow:

```text
Assessment
   ↓
patient sees result
   ↓
patient chooses to seek hospital coordination
   ↓
PatientRequest created
```

This allows a patient to receive the prototype assessment without automatically broadcasting health information to hospitals.

---

# 41C. Patient / Attendant Identity Boundary

The system may be used by the patient or by an attendant acting on behalf of a patient.

Do not assume:

```text
requester == patient
```

The journey model should conceptually distinguish:

```text
patient
requester
relationship_to_patient (if applicable)
```

For the prototype, this can remain a simple field rather than a complex identity-management subsystem.

Do not require a full patient account before proving the core workflow unless authentication is already available.

Use synthetic/demo identities for presentation.

---

# 41D. Location Handling

Stage 1 requires location for candidate generation and routing, but exact patient location is sensitive.

Separate:

```text
patient's private location
```

from:

```text
location information shared with hospitals
```

The prototype must define what is sent during the Stage-1 broadcast.

Minimum default principle:

```text
patient → exact location may be used by the coordination service
hospital request → only the location precision necessary for the prototype's coordination workflow
```

Do not expose exact patient coordinates in the network/admin dashboard.

Do not retain location indefinitely merely because it was used for routing.

---

# 41E. Hospital Capability / Resource / State Semantics

The prototype has three distinct concepts:

## Capability

What the hospital can provide.

Examples:

```text
ICU
Cardiology
Neurology
CT
Emergency Care
```

## Resource Definition

What physical/staff resources the hospital has registered for the coordination system.

Example:

```text
ICU beds: total 30
CT scanners: total 1
```

## Operational State

What is currently known about that resource.

Example:

```text
ICU beds available: 2
CT operational: yes
Neurology specialist status: ON_CALL
```

Never collapse these concepts into `hospital.available = true`.

---

## 41E.1 — Resource Types Need Resource-Specific Semantics

Do not make one universal status enum pretend that every resource behaves identically.

At the data-model level, use a generic resource record but validate allowed fields/statuses according to resource type.

Examples:

```text
ICU BED
- total_count
- available_count
- occupied_count

CT
- operational / offline / maintenance
- optionally queue information later

SPECIALIST
- available / on-call / busy / unavailable
- time window may be added later
```

For MVP, implement only the resource semantics actually required by the demo scenarios.

Do not build a universal hospital resource ontology for the prototype.

---

# 41F. Hospital State Freshness Is Stage-Specific

`last_updated` alone is not enough. The application must define how freshness affects each operation.

The current state can be:

```text
CURRENT
RECENT
STALE
UNKNOWN
```

But the behavior differs by stage.

### Candidate generation

Very stale mandatory capability/resource information should not silently appear as verified current availability.

### Ranking

Staleness can reduce a hospital's ranking or exclude it according to the prototype policy.

### Acceptance

The receiving hospital must re-read its current state before acceptance regardless of the ranking result.

### UI

Display the data age so the user understands what the system knows.

The exact numeric thresholds are prototype configuration, not medical standards.

---

# 41G. State Updates Need Version + Idempotency

For every incoming hospital-state event:

```text
source_event_id
hospital_id
resource_type
source_version/event_version
source_timestamp
```

The state update must be applied only when it is newer than the stored version under the chosen ordering rule.

Duplicate events must not produce duplicate state changes.

This protects against:

```text
duplicate delivery
out-of-order delivery
browser retry
adapter retry
```

The current `hospital_state` is the snapshot; `hospital_state_events` is history.

Do not make the browser responsible for event ordering.

---

# 41H. Referral Engine Snapshot Semantics

A ranking result must be reproducible enough to explain later.

When the engine evaluates a referral, record or associate:

```text
referral_id
engine/policy version
ranking configuration version
evaluation timestamp
candidate hospital IDs
relevant state timestamps/versions
routing result used
```

For the MVP, this can be a compact evaluation/audit record rather than a full copy of every hospital row.

The goal is to answer:

> Why was Hospital A recommended at that moment?

Do not recompute an old explanation using today's hospital state.

---

# 41I. Ranking Policy Contract

The ranking engine must have a named/versioned policy.

Example:

```text
ranking_policy = referral_v1
```

The policy defines:

```text
eligible factors
normalization rules
weights
tie-breaking rules
freshness behavior
```

Prototype weights are engineering assumptions.

Do not call them clinically optimal weights.

Do not modify weights silently between demo runs.

---

# 41I.1 — Ranking Is Not Reservation

The ranking engine computes:

> Best currently feasible candidate according to the prototype policy and available data.

It does not compute:

> Guaranteed future treatment capacity.

It does not reserve a bed.

It does not guarantee admission.

The receiving hospital's acceptance is a separate state transition.

---

# 41J. Stage-2 Referral and Real-World Referral Documentation

The existing ground-level workflow obtained by the team indicates that referral letters can be part of current higher-centre referral practice.

The prototype should therefore model the digital referral as an **augmentation of the referral process**, not silently assume that the existing referral document disappears.

The referral record should retain:

```text
referring hospital
referring clinician
referral reason
clinical summary
required specialty/resources
supporting information
created timestamp
```

If the prototype represents a referral document/letter, label it as a **prototype-generated referral summary**, not as a legally valid national referral document.

Do not claim the software has replaced institutional referral documentation requirements.

---

# 41K. Stage-2 Referral Eligibility and Acceptance Are Different

Three states must remain separate:

```text
ELIGIBLE
```

means:

> The hospital appears able to satisfy the requirements according to current known data.

```text
RECOMMENDED
```

means:

> The ranking policy selected it as a preferred candidate.

```text
ACCEPTED
```

means:

> The receiving hospital has explicitly agreed to coordinate receipt after revalidation.

Do not collapse these into one boolean such as `available = true`.

---

# 41L. Stage-2 Acceptance Revalidation

When a receiving hospital accepts:

```text
referral still pending?
        ↓
current state still satisfies mandatory requirements?
        ↓
actor authorized for this hospital?
        ↓
atomic state transition
        ↓
accepted
```

The recommendation shown earlier is never sufficient by itself for acceptance.

This is both a correctness requirement and a concurrency requirement.

---

# 41M. Resource Contention Boundary

The prototype must not pretend that it owns the hospital's physical resource allocation.

Example:

```text
Hospital A reports ICU available = 1
```

A referral acceptance in our database means:

> Hospital A accepted the coordination request.

It does not mean:

> Our application has physically reserved ICU bed #17.

Actual reservation must be performed by/in coordination with the hospital's authoritative resource-management system in production.

This distinction must be reflected in UI wording, API naming and documentation.

---

# 41N. Hospital Arrival / Stage Boundary

Stage 2 cannot begin merely because Stage 1 is `MATCHED`.

The prototype journey should include explicit states between match and referral:

```text
MATCHED
   ↓
TRAVEL_TO_HOSPITAL_1
   ↓
ARRIVED_AT_HOSPITAL_1
   ↓
UNDER_INITIAL_CARE
   ↓
REFERRAL_DECISION
```

Only the clinician's referral action transitions the journey into Stage 2.

For the prototype, arrival/initial-care states can be controlled by the Hospital 1 dashboard; they do not require clinical-system integration.

---

# 41O. Doctor Override Must Be Auditable

If the UI exposes:

```text
System recommendation
[ Confirm ] [ Override ]
```

an override must record:

```text
overridden_by
overridden_at
override_reason
recommended_hospital
selected_hospital
ranking_policy_version
```

Do not expose an override button unless these actions can actually be recorded.

---

# 41P. Journey Correlation and Duplicate Requests

A patient should not accidentally create multiple active Stage-1 requests from repeated clicks.

At minimum:

```text
active patient request
```

must be checked before creating another one, unless the product explicitly supports multiple simultaneous requests.

Use a journey/request correlation identifier so logs can connect:

```text
Stage-1 request
→ Hospital 1
→ Stage-2 referral
→ Hospital 2
→ transfer
→ handoff
```

Do not use the patient ID alone as the journey identifier.

---

# 41Q. Stage-1 and Stage-2 Broadcast Scope

Do not assume “broadcast to every feasible hospital” without a candidate limit.

Define a prototype policy such as:

```text
candidate radius/search area
→ eligibility
→ optional top-N broadcast limit
```

The exact values are prototype configuration.

The important rule is that the candidate set must be deterministic and explainable.

---

# 41R. External-Service Boundaries

The following services are dependencies, not core business logic:

```text
Hugging Face model
OSRM
OpenStreetMap tiles
Supabase Realtime
```

Wrap them behind application services:

```text
triage/service.py
routing.py
realtime client/service
```

Do not scatter HTTP calls or model-loading code across React components and Flask routes.

Each dependency must have an explicit failure behavior.

---

# 41S. Model Loading and Runtime

The selected transformer must be loaded once per backend process and reused for inference.

Do not load the model once per request.

During development, measure:

```text
model load time
first inference latency
warm inference latency
memory usage
```

Deployment must expose readiness only after the model is loaded if the model is required for Stage-1 requests.

Use:

```text
GET /health
```

for process health and:

```text
GET /ready
```

for dependency/model readiness.

Do not report the service as ready if a required dependency is unavailable.

---

# 41T. Realtime Failure and Recovery Contract

Realtime is an optimization for immediate propagation, not the only method by which the application learns state.

If a realtime connection fails:

```text
connection lost
      ↓
show live-data warning
      ↓
fetch authoritative current state
      ↓
resume subscription
```

Do not attempt to infer the current state from the last event received by the browser.

---

# 41U. Current State vs Event History

The following invariant must hold:

```text
hospital_state
    = current coordination snapshot

hospital_state_events
    = append-only history of accepted state changes
```

The UI reads the current snapshot.

The audit/debug interface can read the history.

The referral engine should normally read the snapshot, not replay the entire event history on every evaluation.

---

# 41V. Demo/Admin Simulator Security Boundary

The network simulator is a **prototype control plane**, not normal hospital authority.

Its ability to modify hospital state must be restricted to the demo/admin role.

Hospital staff may modify only their own hospital's operational state through their permitted interface.

Do not create a generic `update any hospital state` API for the frontend.

---

# 41W. Prototype Ranking Inputs — Final MVP Set

For the first working engine, use only:

```text
1. travel time
2. mandatory capability/resource feasibility
3. relevant specialist availability
4. current operational load
5. state freshness
```

Do not include:

```text
hospital star rating
predicted waiting time
future bed availability
unvalidated clinical quality score
```

The ranking system must remain understandable enough that each factor can be explained to a CSE faculty member.

---

# 44A. Pre-Coding Gates

An AI coding agent must not begin broad implementation until these contracts are explicitly represented in the repository:

```text
1. JOURNEY_STATE_MACHINE
2. STAGE1_REQUEST_STATE_MACHINE
3. STAGE1_RESPONSE/CONFIRMATION_STATE_MACHINE
4. HOSPITAL_CAPABILITY_RESOURCE_STATE_SEMANTICS
5. HOSPITAL_STATE_FRESHNESS_POLICY
6. STAGE1_TRIAGE_OUTPUT_CONTRACT
7. CARE_REQUIREMENT_MAPPING_RULES
8. PATIENT/ATTENDANT_IDENTITY_RULES
9. LOCATION_SHARING_RULES
10. STAGE2_REFERRAL_STATE_MACHINE
11. STAGE2_ACCEPTANCE_REVALIDATION_RULES
12. RESOURCE_RESERVATION_BOUNDARY
13. TRANSFER_STATE_MACHINE
14. API_WRITE/IDEMPOTENCY_RULES
15. RANKING_POLICY_VERSION
16. RANKING_EVALUATION_RECORD
17. REALTIME_FAILURE/RECOVERY_RULES
18. MODEL_RUNTIME/READINESS_RULES
```

If any of these is unclear, the agent must stop and ask/flag the ambiguity rather than choosing behavior silently.

---

# 45. Definition of Done for the Prototype

The prototype is ready for the internal round only when this complete journey can be demonstrated reliably:

```text
PATIENT AT HOME
      ↓
Symptoms
      ↓
Medical-triage transformer
      ↓
Urgency / requirements
      ↓
Nearby feasible hospitals
      ↓
Multiple hospitals receive request
      ↓
Hospitals respond
      ↓
Patient selects
      ↓
Hospital confirms
      ↓
HOSPITAL 1
      ↓
Initial treatment / stabilization
      ↓
Doctor decides referral required
      ↓
Structured referral
      ↓
Hard constraints
      ↓
Dynamic ranking
      ↓
Explainable recommendation
      ↓
Receiving hospitals respond
      ↓
Valid acceptance
      ↓
Transfer
      ↓
Patient received
      ↓
Handoff completed
```

The critical live demonstration must additionally show:

```text
Hospital A ICU = 2
       ↓
Hospital A ICU = 0
       ↓
Realtime update
       ↓
A becomes infeasible
       ↓
Recommendation changes
       ↓
Hospital C becomes the next feasible option
```

That demonstration is the clearest proof that the prototype is a **real-time coordination system**, rather than a static hospital directory with an AI chatbot attached.
