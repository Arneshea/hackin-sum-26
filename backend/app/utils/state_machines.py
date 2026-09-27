"""
Explicit state machine definitions (section 0.1, gate #1-3/10/13 in
section 44A). Kept as one reviewable module rather than scattered
`if status == "X"` checks across routes, so an agent or reviewer can
see the full legal-transition set for each machine in one place.

Five separate machines — never mixed (section 0.1):
  1. JOURNEY_STATE_MACHINE
  2. STAGE1_REQUEST_STATE_MACHINE       (+ response/confirmation, kept
     distinct per section 0.4 even though both live in this module)
  3. HOSPITAL_STATE (freshness/versioning lives in referral_engine/db,
     not here — hospital operational state isn't a finite-state
     machine in the same sense, it's a timestamped observation,
     section 0.7)
  4. STAGE2_REFERRAL_STATE_MACHINE
  5. TRANSFER_STATE_MACHINE
"""

JOURNEY_TRANSITIONS = {
    # AT_HOME has three legal next steps (in addition to CANCELLED):
    #   -> REQUESTING_HOSPITAL      normal Stage-1 matching flow
    #   -> EN_ROUTE_TO_HOSPITAL_1   emergency dispatch (skips matching
    #                               entirely — see routes/emergency.py)
    #   -> REFERRAL_INITIATED       patient-initiated self-referral
    #                               (product decision: patients bring
    #                               their own referral, not always via
    #                               a Stage-1 hospital first — see
    #                               docs/DECISIONS.md)
    "AT_HOME": {"REQUESTING_HOSPITAL", "EN_ROUTE_TO_HOSPITAL_1", "REFERRAL_INITIATED", "CANCELLED"},
    "REQUESTING_HOSPITAL": {"MATCHED_TO_HOSPITAL_1", "CANCELLED"},
    "MATCHED_TO_HOSPITAL_1": {"EN_ROUTE_TO_HOSPITAL_1", "CANCELLED"},
    "EN_ROUTE_TO_HOSPITAL_1": {"ARRIVED_AT_HOSPITAL_1", "CANCELLED"},
    "ARRIVED_AT_HOSPITAL_1": {"UNDER_CARE", "CANCELLED"},
    "UNDER_CARE": {"REFERRAL_INITIATED", "COMPLETED", "CANCELLED"},
    "REFERRAL_INITIATED": {"TRANSFER_TO_HOSPITAL_2", "UNDER_CARE", "CANCELLED"},
    "TRANSFER_TO_HOSPITAL_2": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

STAGE1_REQUEST_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"BROADCASTING", "NO_MATCH", "CANCELLED", "EXPIRED"},
    "BROADCASTING": {"PATIENT_SELECTING", "NO_MATCH", "CANCELLED", "EXPIRED"},
    "PATIENT_SELECTING": {"CONFIRMING", "CANCELLED", "EXPIRED"},
    "CONFIRMING": {"MATCHED", "PATIENT_SELECTING", "CONFIRMATION_FAILED", "CANCELLED"},
    "MATCHED": set(),
    "NO_MATCH": set(),
    "EXPIRED": set(),
    "CANCELLED": set(),
    "CONFIRMATION_FAILED": {"PATIENT_SELECTING", "CANCELLED"},
}

STAGE1_RESPONSE_TRANSITIONS = {
    "PENDING": {"ACCEPTED", "DECLINED", "EXPIRED"},
    "ACCEPTED": {"WITHDRAWN"},
    "DECLINED": set(),
    "WITHDRAWN": set(),
    "EXPIRED": set(),
}

STAGE2_REFERRAL_TRANSITIONS = {
    "DRAFT": {"EVALUATING", "CANCELLED"},
    "EVALUATING": {"PENDING_ACCEPTANCE", "NO_VERIFIED_FEASIBLE_DESTINATION", "CANCELLED"},
    "PENDING_ACCEPTANCE": {"BROADCASTING", "ACCEPTED", "CANCELLED", "EXPIRED"},
    "BROADCASTING": {"ACCEPTED", "DECLINED_ALL", "CANCELLED", "EXPIRED"},
    "ACCEPTED": set(),  # progression continues in TRANSFER_TRANSITIONS
    "DECLINED_ALL": {"EVALUATING", "CANCELLED"},  # re-evaluate remaining candidates
    "NO_VERIFIED_FEASIBLE_DESTINATION": {"EVALUATING", "CANCELLED"},
    "CANCELLED": set(),
    "EXPIRED": set(),
}

STAGE2_RESPONSE_TRANSITIONS = {
    "PENDING": {"ACCEPTED", "DECLINED", "EXPIRED"},
    "ACCEPTED": set(),
    "DECLINED": set(),
    "EXPIRED": set(),
}

TRANSFER_TRANSITIONS = {
    "ACCEPTED": {"TRANSFER_INITIATED"},
    "TRANSFER_INITIATED": {"EN_ROUTE"},
    "EN_ROUTE": {"PATIENT_RECEIVED"},
    "PATIENT_RECEIVED": {"HANDOFF_COMPLETED"},
    "HANDOFF_COMPLETED": set(),
}


class IllegalTransitionError(Exception):
    pass


def _check(transitions_table: dict, current: str, target: str, machine_name: str):
    allowed = transitions_table.get(current)
    if allowed is None:
        raise IllegalTransitionError(f"{machine_name}: unknown current state '{current}'")
    if target not in allowed:
        raise IllegalTransitionError(
            f"{machine_name}: illegal transition {current} -> {target}. "
            f"Allowed: {sorted(allowed) or '(terminal state)'}"
        )


def assert_journey_transition(current: str, target: str):
    _check(JOURNEY_TRANSITIONS, current, target, "JOURNEY_STATE_MACHINE")


def assert_stage1_request_transition(current: str, target: str):
    _check(STAGE1_REQUEST_TRANSITIONS, current, target, "STAGE1_REQUEST_STATE_MACHINE")


def assert_stage1_response_transition(current: str, target: str):
    _check(STAGE1_RESPONSE_TRANSITIONS, current, target, "STAGE1_RESPONSE_STATE_MACHINE")


def assert_stage2_referral_transition(current: str, target: str):
    _check(STAGE2_REFERRAL_TRANSITIONS, current, target, "STAGE2_REFERRAL_STATE_MACHINE")


def assert_stage2_response_transition(current: str, target: str):
    _check(STAGE2_RESPONSE_TRANSITIONS, current, target, "STAGE2_RESPONSE_STATE_MACHINE")


def assert_transfer_transition(current: str, target: str):
    _check(TRANSFER_TRANSITIONS, current, target, "TRANSFER_STATE_MACHINE")
