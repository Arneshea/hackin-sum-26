"""
POST /transfers/<id>/start      -- ACCEPTED -> TRANSFER_INITIATED -> EN_ROUTE
POST /transfers/<id>/received   -- EN_ROUTE -> PATIENT_RECEIVED
POST /handoffs/<id>/complete    -- PATIENT_RECEIVED -> HANDOFF_COMPLETED
                                    (creates the handoffs record)

`<id>` is the transfer id throughout, including the handoff-complete
call, since the prototype does not model ambulance/fleet dispatch as
a separate tracked entity (out of scope — section 4).
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.services.db import get_cursor, record_audit_event
from app.utils.state_machines import assert_transfer_transition, assert_journey_transition

bp = Blueprint("transfers", __name__)


@bp.post("/transfers/<transfer_id>/start")
def start_transfer(transfer_id):
    with get_cursor(commit=True) as cur:
        cur.execute("select * from transfers where id = %s", (transfer_id,))
        transfer = cur.fetchone()
        if transfer is None:
            return jsonify({"error": "NOT_FOUND"}), 404

        assert_transfer_transition(transfer["status"], "TRANSFER_INITIATED")
        assert_transfer_transition("TRANSFER_INITIATED", "EN_ROUTE")

        now = datetime.now(timezone.utc)
        cur.execute(
            "update transfers set status = 'EN_ROUTE', started_at = %s, en_route_at = %s where id = %s",
            (now, now, transfer_id),
        )

    record_audit_event(None, "HOSPITAL_STAFF", "TRANSFER_STARTED", "transfer", transfer_id)
    return jsonify({"status": "EN_ROUTE"}), 200


@bp.post("/transfers/<transfer_id>/received")
def mark_received(transfer_id):
    with get_cursor(commit=True) as cur:
        cur.execute("select * from transfers where id = %s", (transfer_id,))
        transfer = cur.fetchone()
        if transfer is None:
            return jsonify({"error": "NOT_FOUND"}), 404

        assert_transfer_transition(transfer["status"], "PATIENT_RECEIVED")
        cur.execute(
            "update transfers set status = 'PATIENT_RECEIVED', received_at = now() where id = %s",
            (transfer_id,),
        )

    record_audit_event(None, "HOSPITAL_STAFF", "PATIENT_RECEIVED", "transfer", transfer_id)
    return jsonify({"status": "PATIENT_RECEIVED"}), 200


@bp.post("/handoffs/<transfer_id>/complete")
def complete_handoff(transfer_id):
    body = request.get_json(force=True) or {}

    with get_cursor(commit=True) as cur:
        cur.execute("select * from transfers where id = %s", (transfer_id,))
        transfer = cur.fetchone()
        if transfer is None:
            return jsonify({"error": "NOT_FOUND"}), 404

        assert_transfer_transition(transfer["status"], "HANDOFF_COMPLETED")

        cur.execute("select patient_id from referrals where id = %s", (transfer["referral_id"],))
        patient_id = cur.fetchone()["patient_id"]

        cur.execute(
            """
            insert into handoffs
                (referral_id, patient_id, clinical_summary, current_condition,
                 required_specialty, required_resources, relevant_investigations,
                 referring_doctor, completed_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id, completed_at
            """,
            (
                transfer["referral_id"], patient_id,
                body.get("clinical_summary", ""), body.get("current_condition", ""),
                body.get("required_specialty"), body.get("required_resources"),
                body.get("relevant_investigations"), body.get("referring_doctor", ""),
                body.get("completed_by"),
            ),
        )
        handoff_row = cur.fetchone()

        cur.execute(
            "update transfers set status = 'HANDOFF_COMPLETED', handoff_completed_at = now() where id = %s",
            (transfer_id,),
        )

        assert_journey_transition("TRANSFER_TO_HOSPITAL_2", "COMPLETED")
        cur.execute(
            "update journeys set current_status = 'COMPLETED' where journey_id = %s",
            (transfer["journey_id"],),
        )

    record_audit_event(body.get("completed_by"), "HOSPITAL_STAFF", "HANDOFF_COMPLETED", "transfer", transfer_id)
    return jsonify({"handoff_id": handoff_row["id"], "completed_at": handoff_row["completed_at"].isoformat(), "journey_status": "COMPLETED"}), 200
