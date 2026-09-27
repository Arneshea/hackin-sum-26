"""
POST /patients
GET  /patients/<id>
POST /assessments   (Stage-1 triage; step 4.3/4.4)
"""

from flask import Blueprint, jsonify, request

from app.services.db import get_cursor, record_audit_event
from app.triage.service import run_assessment

bp = Blueprint("patients", __name__)


@bp.post("/patients")
def create_patient():
    body = request.get_json(force=True) or {}
    display_name = body.get("display_name")
    if not display_name:
        return jsonify({"error": "display_name is required"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute(
            "insert into patients (display_name, age, sex, abha_id_optional) "
            "values (%s, %s, %s, %s) returning id, created_at",
            (display_name, body.get("age"), body.get("sex"), body.get("abha_id_optional")),
        )
        row = cur.fetchone()

    record_audit_event(None, body.get("requester_role_optional"), "PATIENT_CREATED", "patient", row["id"])
    return jsonify({"id": row["id"], "created_at": row["created_at"].isoformat()}), 201


@bp.get("/patients/<patient_id>")
def get_patient(patient_id):
    with get_cursor() as cur:
        cur.execute("select id, display_name, age, sex, abha_id_optional, created_at from patients where id = %s", (patient_id,))
        row = cur.fetchone()
    if row is None:
        return jsonify({"error": "NOT_FOUND"}), 404
    result = dict(row)
    result["created_at"] = result["created_at"].isoformat()
    return jsonify(result), 200


@bp.post("/assessments")
def create_assessment():
    """
    Runs the Stage-1 triage transformer and the deterministic policy
    layer. `presenting_concerns` is an explicit structured selection
    from the requester (checkboxes in the UI) — it is never derived
    from the triage label itself (section 0.5).
    """
    body = request.get_json(force=True) or {}
    patient_id = body.get("patient_id")
    raw_input = body.get("raw_input", "")
    presenting_concerns = body.get("presenting_concerns", [])

    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    result = run_assessment(patient_id, raw_input, presenting_concerns)

    record_audit_event(
        body.get("requester_user_id_optional"),
        body.get("requester_role_optional"),
        "ASSESSMENT_CREATED",
        "assessment",
        result["assessment_id"],
        {"triage_label": result["triage_label"], "care_pathway": result["care_pathway"]},
    )

    return jsonify(result), 201