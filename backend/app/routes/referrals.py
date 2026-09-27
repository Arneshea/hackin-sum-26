"""
POST /referrals/parse-document -- best-effort extraction from a
                                   scanned referral letter (MedGemma)
POST /referrals                -- patient-initiated creation (see
                                   docs/DECISIONS.md: referrals are
                                   now started by the patient/
                                   attendant, not by hospital staff)
GET  /referrals/<id>
POST /referrals/<id>/accept    -- atomic acceptance (step 7.2/7.3)
POST /referrals/<id>/decline

Product decision (see docs/DECISIONS.md): the referring hospital no
longer creates the Stage-2 referral. The patient/attendant brings
their own referral — either by scanning a doctor's letter (parsed
with MedGemma, then reviewed/edited by the patient before submitting)
or by entering the details manually — and the same referral engine
(app/referral_engine/) evaluates and broadcasts it to candidate
hospitals exactly as before. `referring_hospital_id` is therefore
optional: many self-referrals won't have one at all.
"""

import base64
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.services.db import get_cursor, get_prototype_config, record_audit_event
from app.referral_engine.evaluation import evaluate_referral
from app.triage.document_parser import parse_referral_document
from app.utils.state_machines import assert_journey_transition, assert_stage2_referral_transition

bp = Blueprint("referrals", __name__)


@bp.post("/referrals/parse-document")
def parse_document():
    """
    Best-effort extraction only. The frontend must show every field
    back to the patient/attendant for review and editing before
    POSTing /referrals — this endpoint never creates a referral by
    itself, and a misread field here must not silently become a
    submitted referral (see app/triage/document_parser.py docstring).
    """
    body = request.get_json(force=True) or {}
    image_b64 = body.get("image_base64")
    extra_text = body.get("extra_text", "")

    if image_b64:
        try:
            base64.b64decode(image_b64, validate=True)
        except Exception:
            return jsonify({"error": "image_base64 is not valid base64"}), 400

    result = parse_referral_document(image_b64, extra_text)
    if not result.ok:
        return jsonify({
            "ok": False,
            "error": result.error or "Could not read the document",
            "raw_model_output": result.raw_model_output,
        }), 200  # 200: this is an expected, handleable outcome, not a server error

    return jsonify({
        "ok": True,
        "reason_for_referral": result.reason_for_referral,
        "clinical_summary": result.clinical_summary,
        "referring_doctor_name": result.referring_doctor_name,
        "requirements": result.requirements,
    }), 200


@bp.post("/referrals")
def create_referral():
    """
    Patient-initiated referral creation. `journey_id` is optional:

      - If the patient already has an active journey at UNDER_CARE
        (e.g. they went through Stage-1 first), pass it and the
        journey transitions UNDER_CARE -> REFERRAL_INITIATED.
      - Otherwise (the common self-referral case: patient already has
        a referral letter from an outside doctor and is starting
        fresh) a new journey is created directly at REFERRAL_INITIATED
        — see the AT_HOME -> REFERRAL_INITIATED transition added to
        the journey state machine for this.
    """
    body = request.get_json(force=True) or {}
    patient_id = body.get("patient_id")
    journey_id = body.get("journey_id")
    referring_hospital_id = body.get("referring_hospital_id")  # optional now
    referring_doctor_name = body.get("referring_doctor_name")
    requirements = body.get("requirements", [])
    origin_lat = body.get("origin_lat")
    origin_lon = body.get("origin_lon")
    source_document_note = body.get("source_document_note")

    if patient_id is None or origin_lat is None or origin_lon is None:
        return jsonify({"error": "patient_id, origin_lat, origin_lon are required"}), 400
    if not requirements:
        return jsonify({"error": "at least one requirement is needed to search for a hospital"}), 400

    response_timeout = get_prototype_config("stage2_response_timeout_seconds", 180)

    with get_cursor(commit=True) as cur:
        if journey_id:
            cur.execute("select patient_id, current_status from journeys where journey_id = %s", (journey_id,))
            journey = cur.fetchone()
            if journey is None:
                return jsonify({"error": "JOURNEY_NOT_FOUND"}), 404
            if journey["current_status"] != "UNDER_CARE":
                return jsonify({"error": "JOURNEY_NOT_UNDER_CARE", "current_status": journey["current_status"]}), 409
            assert_journey_transition("UNDER_CARE", "REFERRAL_INITIATED")
        else:
            cur.execute(
                "insert into journeys (patient_id, current_stage, current_status) "
                "values (%s, 'STAGE2', 'AT_HOME') returning journey_id",
                (patient_id,),
            )
            journey_id = cur.fetchone()["journey_id"]
            assert_journey_transition("AT_HOME", "REFERRAL_INITIATED")

        cur.execute(
            """
            insert into referrals
                (journey_id, patient_id, referring_hospital_id, initiated_by,
                 referring_doctor_name, origin_lat, origin_lon, source_document_note,
                 urgency, reason_for_referral, clinical_summary, created_by, expires_at, status)
            values (%s, %s, %s, 'PATIENT', %s, %s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT')
            returning id, created_at
            """,
            (
                journey_id, patient_id, referring_hospital_id,
                referring_doctor_name, origin_lat, origin_lon, source_document_note,
                body.get("urgency", "urgent"), body.get("reason_for_referral", ""),
                body.get("clinical_summary", ""), body.get("created_by"),
                datetime.now(timezone.utc) + timedelta(seconds=response_timeout),
            ),
        )
        referral_row = cur.fetchone()
        referral_id = referral_row["id"]

        for req in requirements:
            cur.execute(
                """
                insert into referral_requirements
                    (referral_id, requirement_type, value_optional, operator, quantity_optional, mandatory)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    referral_id, req["requirement_type"], req.get("value_optional"),
                    req.get("operator", "PRESENT"), req.get("quantity_optional"), req.get("mandatory", True),
                ),
            )

        cur.execute(
            "update journeys set current_status = 'REFERRAL_INITIATED', referral_id = %s where journey_id = %s",
            (referral_id, journey_id),
        )
        assert_stage2_referral_transition("DRAFT", "EVALUATING")
        cur.execute("update referrals set status = 'EVALUATING' where id = %s", (referral_id,))

    record_audit_event(body.get("created_by"), "PATIENT", "REFERRAL_CREATED", "referral", referral_id)

    return jsonify(_evaluate_and_broadcast(referral_id, origin_lat, origin_lon, requirements)), 201


def _evaluate_and_broadcast(referral_id, origin_lat, origin_lon, requirements):
    radius_km = get_prototype_config("candidate_search_radius_km", 25)
    top_n = get_prototype_config("stage2_broadcast_top_n", 5)
    response_timeout = get_prototype_config("stage2_response_timeout_seconds", 180)

    result = evaluate_referral(referral_id, origin_lat, origin_lon, requirements, radius_km)

    with get_cursor(commit=True) as cur:
        if result["status"] == "NO_VERIFIED_FEASIBLE_DESTINATION":
            assert_stage2_referral_transition("EVALUATING", "NO_VERIFIED_FEASIBLE_DESTINATION")
            cur.execute("update referrals set status = 'NO_VERIFIED_FEASIBLE_DESTINATION' where id = %s", (referral_id,))
        else:
            assert_stage2_referral_transition("EVALUATING", "PENDING_ACCEPTANCE")
            cur.execute("update referrals set status = 'PENDING_ACCEPTANCE' where id = %s", (referral_id,))
            for candidate in result["eligible"][:top_n]:
                cur.execute(
                    """
                    insert into referral_responses (referral_id, hospital_id, status, expires_at)
                    values (%s, %s, 'PENDING', %s)
                    on conflict (referral_id, hospital_id) do nothing
                    """,
                    (referral_id, candidate["hospital_id"], datetime.now(timezone.utc) + timedelta(seconds=response_timeout)),
                )

    record_audit_event(None, None, "REFERRAL_BROADCAST", "referral", referral_id, {"status": result["status"]})
    result["referral_id"] = referral_id
    return result


@bp.get("/hospitals/<hospital_id>/referral-responses")
def list_hospital_referral_responses(hospital_id):
    """Incoming Stage-2 referrals for the hospital dashboard (step 5.2 / 31)."""
    with get_cursor() as cur:
        cur.execute(
            """
            select rr.*, r.reason_for_referral, r.clinical_summary, r.urgency,
                   r.status as referral_status, r.referring_doctor_name, r.initiated_by
            from referral_responses rr
            join referrals r on r.id = rr.referral_id
            where rr.hospital_id = %s
            order by rr.expires_at desc nulls last
            limit 50
            """,
            (hospital_id,),
        )
        rows = cur.fetchall()

    result = []
    for r in rows:
        d = dict(r)
        if d.get("responded_at"):
            d["responded_at"] = d["responded_at"].isoformat()
        if d.get("expires_at"):
            d["expires_at"] = d["expires_at"].isoformat()
        result.append(d)
    return jsonify(result), 200


@bp.get("/patients/<patient_id>/referrals")
def list_patient_referrals(patient_id):
    """A patient's own referral history, for the patient-side referral screen."""
    with get_cursor() as cur:
        cur.execute(
            "select id, status, reason_for_referral, created_at from referrals "
            "where patient_id = %s order by created_at desc",
            (patient_id,),
        )
        rows = cur.fetchall()
    return jsonify([{**dict(r), "created_at": r["created_at"].isoformat()} for r in rows]), 200


@bp.get("/referrals/<referral_id>")
def get_referral(referral_id):
    with get_cursor() as cur:
        cur.execute("select * from referrals where id = %s", (referral_id,))
        referral = cur.fetchone()
        if referral is None:
            return jsonify({"error": "NOT_FOUND"}), 404
        cur.execute("select * from referral_requirements where referral_id = %s", (referral_id,))
        requirements = cur.fetchall()
        cur.execute(
            """
            select rr.*, h.name as hospital_name from referral_responses rr
            join hospitals h on h.id = rr.hospital_id
            where rr.referral_id = %s
            """,
            (referral_id,),
        )
        responses = cur.fetchall()
        cur.execute(
            "select * from referral_evaluations where referral_id = %s order by evaluated_at desc limit 20",
            (referral_id,),
        )
        evaluations = cur.fetchall()

    def iso(d, keys):
        d = dict(d)
        for k in keys:
            if d.get(k):
                d[k] = d[k].isoformat()
        return d

    result = iso(referral, ["created_at", "expires_at", "accepted_at_optional"])
    result["requirements"] = [dict(r) for r in requirements]
    result["responses"] = [iso(r, ["responded_at", "expires_at"]) for r in responses]
    result["evaluations"] = [iso(e, ["evaluated_at"]) for e in evaluations]
    return jsonify(result), 200


@bp.post("/referrals/<referral_id>/accept")
def accept_referral(referral_id):
    """Atomic acceptance (step 7.2/7.3) — race-safe at the DB level."""
    body = request.get_json(force=True) or {}
    hospital_id = body.get("hospital_id")
    if not hospital_id:
        return jsonify({"error": "hospital_id is required"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("select accept_referral(%s, %s) as won", (referral_id, hospital_id))
        won = cur.fetchone()["won"]

        if not won:
            return jsonify({"error": "ALREADY_DECIDED", "detail": "Another hospital already won or referral is not pending"}), 409

        cur.execute(
            "update referral_responses set status = 'EXPIRED' "
            "where referral_id = %s and hospital_id != %s and status = 'PENDING'",
            (referral_id, hospital_id),
        )

        cur.execute("select journey_id from referrals where id = %s", (referral_id,))
        journey_id = cur.fetchone()["journey_id"]
        cur.execute(
            "update journeys set current_status = 'TRANSFER_TO_HOSPITAL_2', stage2_hospital_id = %s where journey_id = %s",
            (hospital_id, journey_id),
        )
        cur.execute(
            "insert into transfers (referral_id, journey_id, status) values (%s, %s, 'ACCEPTED') returning id",
            (referral_id, journey_id),
        )
        transfer_id = cur.fetchone()["id"]

    record_audit_event(None, "HOSPITAL_STAFF", "REFERRAL_ACCEPTED", "referral", referral_id, {"hospital_id": hospital_id})
    return jsonify({"status": "ACCEPTED", "transfer_id": transfer_id}), 200


@bp.post("/referrals/<referral_id>/decline")
def decline_referral(referral_id):
    body = request.get_json(force=True) or {}
    hospital_id = body.get("hospital_id")
    reason = body.get("reason", "OTHER")

    with get_cursor(commit=True) as cur:
        cur.execute(
            "update referral_responses set status = 'DECLINED', reason = %s, responded_at = now() "
            "where referral_id = %s and hospital_id = %s and status = 'PENDING' returning id",
            (reason, referral_id, hospital_id),
        )
        if cur.fetchone() is None:
            return jsonify({"error": "RESPONSE_NOT_PENDING"}), 409

        cur.execute(
            "select count(*) as pending_count from referral_responses "
            "where referral_id = %s and status = 'PENDING'",
            (referral_id,),
        )
        pending_count = cur.fetchone()["pending_count"]

    record_audit_event(None, "HOSPITAL_STAFF", "REFERRAL_DECLINED", "referral", referral_id, {"hospital_id": hospital_id, "reason": reason})

    if pending_count == 0:
        # Rerouting after decline (section 3 / step 7.4): re-run the
        # engine against the referral's original requirements/origin.
        return jsonify(_reevaluate_after_decline(referral_id)), 200

    return jsonify({"status": "DECLINED", "remaining_pending": pending_count}), 200


def _reevaluate_after_decline(referral_id):
    with get_cursor() as cur:
        cur.execute("select origin_lat, origin_lon from referrals where id = %s", (referral_id,))
        referral = cur.fetchone()
        cur.execute(
            "select requirement_type, operator, quantity_optional, mandatory from referral_requirements where referral_id = %s",
            (referral_id,),
        )
        requirements = [dict(r) for r in cur.fetchall()]

    with get_cursor(commit=True) as cur:
        assert_stage2_referral_transition("BROADCASTING", "DECLINED_ALL")
        cur.execute("update referrals set status = 'DECLINED_ALL' where id = %s", (referral_id,))
        assert_stage2_referral_transition("DECLINED_ALL", "EVALUATING")
        cur.execute("update referrals set status = 'EVALUATING' where id = %s", (referral_id,))

    return _evaluate_and_broadcast(referral_id, referral["origin_lat"], referral["origin_lon"], requirements)
