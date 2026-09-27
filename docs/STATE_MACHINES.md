# STATE_MACHINES.md

Five separate state machines (section 0.1) — kept explicit and
separate in `backend/app/utils/state_machines.py`. Never inferred
from combinations of other fields; every transition goes through an
`assert_*_transition()` call before being written.

## 1. Journey (the parent workflow, step 4.9)

```
AT_HOME -> REQUESTING_HOSPITAL -> MATCHED_TO_HOSPITAL_1
  -> EN_ROUTE_TO_HOSPITAL_1 -> ARRIVED_AT_HOSPITAL_1 -> UNDER_CARE
  -> REFERRAL_INITIATED -> TRANSFER_TO_HOSPITAL_2 -> COMPLETED
```
CANCELLED is reachable from every non-terminal state.

`AT_HOME` has two additional direct transitions beyond
`REQUESTING_HOSPITAL`, added for two new requirements:

- `AT_HOME -> EN_ROUTE_TO_HOSPITAL_1` — the emergency-dispatch button
  skips Stage-1 matching entirely (see `routes/emergency.py` and
  `docs/DECISIONS.md`).
- `AT_HOME -> REFERRAL_INITIATED` — a patient starting a self-referral
  (e.g. from an outside doctor's letter) without having gone through
  Stage-1 in this system at all (see `routes/referrals.py`).

## 2. Stage-1 patient request

```
DRAFT -> SUBMITTED -> BROADCASTING -> PATIENT_SELECTING -> CONFIRMING -> MATCHED
```
Side branches: NO_MATCH, EXPIRED, CANCELLED, CONFIRMATION_FAILED (which
returns to PATIENT_SELECTING so the patient can pick a different
already-accepted hospital, per step 4.12).

## 2b. Stage-1 hospital response

```
PENDING -> ACCEPTED -> WITHDRAWN
PENDING -> DECLINED
PENDING -> EXPIRED
```

## 3. Hospital operational state

Not a finite-state machine in the traditional sense — it's a
timestamped observation with a monotonic version (section 0.7). See
`DATA_MODEL.md` for its update contract.

## 4. Stage-2 referral

```
DRAFT -> EVALUATING -> PENDING_ACCEPTANCE -> BROADCASTING -> ACCEPTED
EVALUATING -> NO_VERIFIED_FEASIBLE_DESTINATION -> EVALUATING (retry)
BROADCASTING -> DECLINED_ALL -> EVALUATING (retry after all decline)
```
CANCELLED/EXPIRED reachable from most non-terminal states.

## 4b. Stage-2 referral response

```
PENDING -> ACCEPTED
PENDING -> DECLINED
PENDING -> EXPIRED
```

## 5. Transfer / handoff

```
ACCEPTED -> TRANSFER_INITIATED -> EN_ROUTE -> PATIENT_RECEIVED -> HANDOFF_COMPLETED
```
Strictly linear, no skipping (step 22.2 test: `COMPLETED -> ACCEPTED`
is invalid and raises `IllegalTransitionError`).

## Atomicity (step 7.3)

Two transitions are race-sensitive and are therefore implemented as
single conditional SQL statements in
`database/migrations/002_atomic_transitions.sql`, never as
read-then-write application logic:

- `accept_referral(referral_id, hospital_id)` — exactly one hospital
  can win a `PENDING_ACCEPTANCE -> ACCEPTED` transition.
- `select_hospital_for_request` / `confirm_hospital_match` — the
  Stage-1 mutual-selection handshake.
