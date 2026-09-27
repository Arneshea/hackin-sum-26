"""
Stage-1 policy layer (step 4.6 / step 4.7 / section 0.5).

This is the ONLY place a triage label is translated into anything
downstream, and it deliberately stops at a broad "care pathway" —
it does NOT map an urgency label to a specialty or resource
requirement. That would be an invented clinical inference
(`urgent -> cardiology`), which the spec explicitly forbids.

Structured requirements (ICU / NEUROLOGY / CT, etc.) only ever come
from an explicit, separate structured input: here, the patient/
attendant's own selection of a presenting-concern category, collected
alongside — not derived from — the free-text triage assessment.
"""

from app.config import get_config

CARE_PATHWAY_BY_LABEL = {
    "URGENT": "EMERGENCY_CARE_PATHWAY",
    "CONSULT_GP": "NON_EMERGENCY_CLINICAL_ACCESS_PATHWAY",
    "SELF_MONITOR": "NON_EMERGENCY_GUIDANCE",
    "ASSESSMENT_UNAVAILABLE": "MANUAL_TRIAGE_FALLBACK",
}

# Explicit, structured presenting-concern -> requirement vocabulary
# (step 4.7). This is a UI-level checklist choice made by the patient/
# attendant (e.g. "suspected stroke symptoms", "chest pain"), NOT an
# inference from the triage model's urgency label. MVP supports only
# simple mandatory AND requirements (step 6.3) — no boolean/optimization
# expression engine.
REQUIREMENT_RULES_BY_PRESENTING_CONCERN = {
    "SUSPECTED_STROKE": [
        {"requirement_type": "NEUROLOGY", "operator": "PRESENT", "mandatory": True},
        {"requirement_type": "CT", "operator": "PRESENT", "mandatory": True},
    ],
    "SEVERE_TRAUMA": [
        {"requirement_type": "ICU", "operator": "PRESENT", "mandatory": True},
    ],
    "CARDIAC_SYMPTOMS": [
        {"requirement_type": "CARDIOLOGY", "operator": "PRESENT", "mandatory": True},
    ],
    "GENERAL_EMERGENCY": [
        {"requirement_type": "EMERGENCY", "operator": "PRESENT", "mandatory": True},
    ],
}


def resolve_care_pathway(triage_label: str) -> str:
    return CARE_PATHWAY_BY_LABEL.get(triage_label, "MANUAL_TRIAGE_FALLBACK")


def resolve_requirements(presenting_concerns: list[str]) -> list[dict]:
    """
    `presenting_concerns` must be explicit structured selections made
    by the requester (e.g. checkbox values), never inferred from the
    triage model's free-text output. Unknown concerns are ignored
    rather than guessed at.
    """
    requirements: list[dict] = []
    seen_types = set()
    for concern in presenting_concerns:
        for rule in REQUIREMENT_RULES_BY_PRESENTING_CONCERN.get(concern, []):
            if rule["requirement_type"] not in seen_types:
                requirements.append(rule)
                seen_types.add(rule["requirement_type"])
    if not requirements:
        # Always require baseline emergency capability if nothing else
        # was explicitly selected, so Stage-1 matching has something
        # concrete to filter on.
        requirements.append({"requirement_type": "EMERGENCY", "operator": "PRESENT", "mandatory": True})
    return requirements


def policy_version() -> str:
    return get_config().TRIAGE_POLICY_VERSION
