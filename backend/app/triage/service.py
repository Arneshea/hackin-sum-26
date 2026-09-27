"""
Stage-1 triage service (step 4.3 / step 4.4).

Orchestrates: raw text -> transformer inference -> policy layer ->
persisted assessment record. This is the only entry point routes
should call; nothing outside this module talks to the model directly.
"""

from app.services.db import get_cursor
from app.triage import model, policy


def run_assessment(patient_id: str, raw_input: str, presenting_concerns: list[str]) -> dict:
    result = model.infer(raw_input)
    care_pathway = policy.resolve_care_pathway(result.label)
    requirements = policy.resolve_requirements(presenting_concerns)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            insert into assessments
                (patient_id, raw_input, triage_label, model_name, model_version,
                 model_scores_optional, policy_version)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning id, created_at
            """,
            (
                patient_id,
                raw_input,
                result.label,
                result.model_name,
                result.model_version,
                _to_json(result.scores),
                policy.policy_version(),
            ),
        )
        row = cur.fetchone()

    return {
        "assessment_id": row["id"],
        "created_at": row["created_at"].isoformat(),
        "triage_label": result.label,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "model_scores": result.scores,  # None unless the model exposed real scores
        "care_pathway": care_pathway,
        "requirements": requirements,
        "policy_version": policy.policy_version(),
    }


def _to_json(scores):
    import json

    return json.dumps(scores) if scores is not None else None
