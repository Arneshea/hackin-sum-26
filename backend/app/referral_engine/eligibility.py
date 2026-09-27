"""
Eligibility filtering (step 6.2 / step 6.3). Hard constraints precede
ranking (section 6.3): a candidate that fails ANY mandatory
requirement is rejected before scoring, with an explicit reason.

MVP requirement semantics: mandatory AND only, no general boolean/
optimization expression engine (step 6.3).
"""

from dataclasses import dataclass, field
from typing import Optional

from app.referral_engine.freshness import freshness_category


@dataclass
class CandidateSnapshot:
    hospital_id: str
    capabilities: set  # capability strings the hospital has
    state_by_resource: dict  # resource_type -> hospital_state row (dict)


@dataclass
class EligibilityResult:
    hospital_id: str
    eligible: bool
    rejection_reason: Optional[str] = None
    freshness_by_resource: dict = field(default_factory=dict)


def _state_satisfies(state_row: dict, requirement: dict, category: str) -> bool:
    """
    Whether the current observed state satisfies a mandatory
    requirement, given its freshness. A STALE/UNKNOWN observation for
    a mandatory requirement is treated as not-satisfying by default —
    this is itself a documented prototype policy choice (step 6.4),
    not a claim about the physical hospital.
    """
    if category in ("STALE", "UNKNOWN"):
        return False

    measurement_type = state_row["measurement_type"]
    status = state_row["status"]

    if measurement_type == "COUNT":
        available = state_row.get("available_count_optional") or 0
        min_qty = requirement.get("quantity_optional") or 1
        return status == "AVAILABLE" and available >= min_qty
    if measurement_type == "BINARY_SERVICE":
        return status == "OPERATIONAL"
    if measurement_type == "PERSONNEL_AVAILABILITY":
        return status in ("AVAILABLE", "ON_CALL")
    return False


def evaluate_candidate(candidate: CandidateSnapshot, requirements: list[dict]) -> EligibilityResult:
    freshness_by_resource = {}

    for req in requirements:
        if not req.get("mandatory", True):
            continue  # MVP scope: only mandatory AND requirements are enforced

        req_type = req["requirement_type"]

        if req_type not in candidate.capabilities:
            return EligibilityResult(
                hospital_id=candidate.hospital_id,
                eligible=False,
                rejection_reason=f"NO_{req_type}_CAPABILITY",
            )

        state_row = candidate.state_by_resource.get(req_type)
        if state_row is None:
            return EligibilityResult(
                hospital_id=candidate.hospital_id,
                eligible=False,
                rejection_reason=f"{req_type}_STATE_UNKNOWN",
            )

        category = freshness_category(state_row["updated_at"])
        freshness_by_resource[req_type] = category

        if not _state_satisfies(state_row, req, category):
            reason = f"{req_type}_UNAVAILABLE" if category not in ("STALE", "UNKNOWN") else f"{req_type}_STATE_STALE"
            return EligibilityResult(
                hospital_id=candidate.hospital_id,
                eligible=False,
                rejection_reason=reason,
                freshness_by_resource=freshness_by_resource,
            )

    return EligibilityResult(
        hospital_id=candidate.hospital_id,
        eligible=True,
        freshness_by_resource=freshness_by_resource,
    )
