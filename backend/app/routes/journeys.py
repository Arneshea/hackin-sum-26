"""
GET /journeys/<id>

Not in the original section 32 API list by name, but needed by every
tracking/dashboard screen to read the parent workflow record (step
4.9). Read-only; all journey status transitions happen as side
effects of the Stage-1/Stage-2/transfer routes, never written here.
"""

from flask import Blueprint, jsonify

from app.services.db import get_cursor, record_audit_event
from app.utils.state_machines import assert_journey_transition

bp = Blueprint("journeys", __name__)


@bp.get("/journeys/<journey_id>")
def get_journey(journey_id):
    with get_cursor() as cur:
        cur.execute("select * from journeys where journey_id = %s", (journey_id,))
        journey = cur.fetchone()
        if journey is None:
            return jsonify({"error": "NOT_FOUND"}), 404

        cur.execute("select id, name, latitude, longitude from hospitals where id = %s", (journey["stage1_hospital_id"],)) if journey["stage1_hospital_id"] else None
        stage1_hospital = cur.fetchone() if journey["stage1_hospital_id"] else None

        cur.execute("select id, name, latitude, longitude from hospitals where id = %s", (journey["stage2_hospital_id"],)) if journey["stage2_hospital_id"] else None
        stage2_hospital = cur.fetchone() if journey["stage2_hospital_id"] else None

        transfer = None
        if journey["referral_id"]:
            cur.execute("select * from transfers where journey_id = %s order by created_at desc limit 1", (journey_id,))
            transfer = cur.fetchone()

    result = dict(journey)
    result["created_at"] = result["created_at"].isoformat()
    result["updated_at"] = result["updated_at"].isoformat()
    result["stage1_hospital"] = dict(stage1_hospital) if stage1_hospital else None
    result["stage2_hospital"] = dict(stage2_hospital) if stage2_hospital else None
    if transfer:
        t = dict(transfer)
        for f in ("started_at", "en_route_at", "received_at", "handoff_completed_at", "created_at", "updated_at"):
            if t.get(f):
                t[f] = t[f].isoformat()
        result["transfer"] = t
    else:
        result["transfer"] = None

    return jsonify(result), 200


def _advance(journey_id, target_status):
    """
    Shared helper for the manual clinical-progression transitions
    (step 5.1/5.3): the application never infers "patient arrived" or
    "referral required" automatically — a human explicitly advances
    the journey through these endpoints.
    """
    with get_cursor(commit=True) as cur:
        cur.execute("select current_status from journeys where journey_id = %s", (journey_id,))
        journey = cur.fetchone()
        if journey is None:
            return None, ("NOT_FOUND", 404)

        try:
            assert_journey_transition(journey["current_status"], target_status)
        except Exception as exc:
            return None, (str(exc), 409)

        cur.execute("update journeys set current_status = %s where journey_id = %s", (target_status, journey_id))
    return target_status, None


@bp.post("/journeys/<journey_id>/mark-en-route")
def mark_en_route(journey_id):
    status, err = _advance(journey_id, "EN_ROUTE_TO_HOSPITAL_1")
    if err:
        return jsonify({"error": err[0]}), err[1]
    record_audit_event(None, None, "JOURNEY_EN_ROUTE_TO_HOSPITAL_1", "journey", journey_id)
    return jsonify({"status": status}), 200


@bp.post("/journeys/<journey_id>/mark-arrived")
def mark_arrived(journey_id):
    status, err = _advance(journey_id, "ARRIVED_AT_HOSPITAL_1")
    if err:
        return jsonify({"error": err[0]}), err[1]
    record_audit_event(None, None, "JOURNEY_ARRIVED_AT_HOSPITAL_1", "journey", journey_id)
    return jsonify({"status": status}), 200


@bp.post("/journeys/<journey_id>/mark-under-care")
def mark_under_care(journey_id):
    status, err = _advance(journey_id, "UNDER_CARE")
    if err:
        return jsonify({"error": err[0]}), err[1]
    record_audit_event(None, None, "JOURNEY_UNDER_CARE", "journey", journey_id)
    return jsonify({"status": status}), 200


@bp.get("/hospitals/<hospital_id>/journeys")
def list_hospital_journeys(hospital_id):
    """
    Journeys relevant to a given hospital, for the Hospital-1 and
    Receiving-hospital dashboards (step 5.2 / section 31).
    """
    with get_cursor() as cur:
        cur.execute(
            """
            select j.*, p.display_name as patient_display_name
            from journeys j
            join patients p on p.id = j.patient_id
            where j.stage1_hospital_id = %s or j.stage2_hospital_id = %s
            order by j.updated_at desc
            """,
            (hospital_id, hospital_id),
        )
        rows = cur.fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat()
        d["updated_at"] = d["updated_at"].isoformat()
        result.append(d)
    return jsonify(result), 200
