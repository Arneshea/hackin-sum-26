# DATA_MODEL.md

This documents the schema in `database/migrations/001_init_schema.sql`
and the derived concepts the referral engine uses. See that file for
the authoritative column list; this document explains the *meaning*
behind the harder design choices.

## Capability vs. state (section 6.2)

- `hospital_capabilities` — relatively static. "Can this hospital ever
  provide ICU care?"
- `hospital_resources` — the resource's measurement definition
  (`COUNT`, `BINARY_SERVICE`, or `PERSONNEL_AVAILABILITY`) and, for
  `COUNT` resources, the total inventory size.
- `hospital_state` — the latest observed value. "Is ICU available
  *right now*, and how many beds?"

These are never collapsed into one table or one concept.

## Measurement-type semantics

| measurement_type | valid `status` values | example |
|---|---|---|
| COUNT | AVAILABLE, UNAVAILABLE | ICU: `AVAILABLE`, available_count=2, total_count=10 |
| BINARY_SERVICE | OPERATIONAL, DOWN | CT: `OPERATIONAL` |
| PERSONNEL_AVAILABILITY | AVAILABLE, ON_CALL, UNAVAILABLE | Neurology specialist: `ON_CALL` |

A combination like `ICU = ON_CALL` is meaningless and must never be
produced by application code (step 2.4).

## Operational load / resource headroom (step 2.6, step 6.5)

The spec requires that if an "operational load" figure is used in
ranking, its exact definition must be documented — never an
unexplained percentage.

**This prototype's definition:** for a mandatory `COUNT`-type
requirement (e.g. ICU), *resource headroom* =
`available_count_optional / total_count_optional` at evaluation time,
computed only for resources actually named in the referral's
requirements. This is used directly as a ranking factor
(`resource_headroom` in `ranking_weights_v1`). The spec's separate
"current operational load" ranking factor is **not** scored as a
distinct input in this MVP — see
`backend/app/referral_engine/ranking.py`'s module docstring for the
reasoning: scoring both headroom and a load figure derived from the
same underlying number would double-count one signal. If a future
pass wants a genuinely independent operational-load metric (e.g.
overall bed occupancy across all services, not just the mandatory
resource), it must be defined here first, with its own data source,
before being added to `ranking_weights_v1`.

This value is never presented to a clinician as a "clinical score" —
UI copy refers to it only as "resource availability".

## State freshness (step 2.7, step 6.4)

`freshness_category(updated_at)` in
`backend/app/referral_engine/freshness.py` derives one of `CURRENT`,
`RECENT`, `STALE`, `UNKNOWN` from the `stale_data_threshold_seconds`
prototype-config value (defaults: current ≤60s, recent ≤300s, stale
≤1800s, else unknown). These thresholds are prototype policy, not a
medical standard, and are documented here per step 6.4's requirement.

`STALE` or `UNKNOWN` freshness on a *mandatory* requirement causes
eligibility rejection (`eligibility.py`) — the prototype's policy
choice is to treat unverifiable state as unavailable rather than
optimistically assume it's still good.

## Idempotency and monotonic versioning (step 2.8)

Every `hospital_state` row carries a `version` that only increments.
`apply_hospital_state_update()` (in
`002_atomic_transitions.sql`) is the only way state is written; it:

1. Checks whether `(hospital_id, resource_type, source,
   source_event_id)` was already applied — if so, no-op (idempotent
   retries are safe).
2. Otherwise increments `version` and appends a row to
   `hospital_state_events` recording the old and new value.

## Requirement vocabulary (step 4.7, step 6.3)

Requirements are simple mandatory-AND tuples:
`{requirement_type, operator, quantity_optional, mandatory}`. There is
no boolean expression engine (no OR, no nested groups) — this is a
deliberate MVP scope limit, not an oversight.

## Reproducible evaluation (step 6.9)

Every ranking run over a referral writes one `referral_evaluations`
row per candidate hospital, capturing the exact factors, state
versions, and routing snapshot used — so "why was Hospital A ranked
above Hospital B at that time?" is always answerable from stored data,
not just current live state.

## Patient-initiated referrals (changed requirement)

`referrals.referring_hospital_id` is nullable and `referrals` gained
`initiated_by` (`'PATIENT'` default | `'HOSPITAL'`),
`referring_doctor_name`, `origin_lat`/`origin_lon`, and
`source_document_note`. A referral's origin point is now the
patient's own location at the time of the referral, not a referring
hospital's fixed address — since there often isn't one. See
`docs/DECISIONS.md` for the full reasoning.

## Emergency dispatch table

`emergency_dispatches` is intentionally NOT part of the Stage-1
`patient_requests` state machine — it's a simple append-mostly audit
record of "an ambulance was dispatched to hospital X at time Y,"
written by `POST /emergency-dispatch`. It has its own `status`
(`DISPATCHED` | `NO_HOSPITAL_FOUND`), unrelated to
`patient_request_status`, because the emergency flow has no
negotiation states to represent (no PENDING/ACCEPTED/DECLINED — see
`docs/DECISIONS.md`).
