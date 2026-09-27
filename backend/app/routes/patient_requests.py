"""
POST /patient-requests
GET  /patient-requests/<id>
POST /patient-requests/<id>/select
POST /patient-requests/<id>/cancel

POST /patient-request-responses/<id>/accept
POST /patient-request-responses/<id>/decline
POST /patient-request-responses/<id>/confirm

Implements the two-sided Stage-1 match (section 0.3):
  request -> hospitals respond -> patient selects among ACCEPTED
  -> selected hospital revalidates + confirms -> MATCHED
using the database-level atomic functions in
002_atomic_transitions.sql so the race protection lives in Postgres,
not in Flask or React (step 4.12).
"""

import math
from datetime import datetime, timedelta, timezone

import psycopg2.errors
from flask import Blueprint, jsonify, request

from app.services.db import get_cursor, get_prototype_config, record_audit_event
from app.services.routing import get_travel_estimate
from app.utils.state_machines import assert_journey_transition, assert_stage1_request_transition

bp = Blueprint("patient_requests", __name__)


def _distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@bp.post("/patient-requests")
def create_patient_request():
    body = request.get_json(force=True) or {}
    patient_id = body.get("patient_id")
    location_lat = body.get("location_lat")
    location_lon = body.get("location_lon")
    urgency = body.get("urgency", "unknown")
    symptom_summary = body.get("symptom_summary", "")
    requirements = body.get("requirements", [])

    if not all([patient_id, location_lat is not None, location_lon is not None]):
        return jsonify({"error": "patient_id, location_lat, location_lon are required"}), 400

    radius_km = get_prototype_config("candidate_search_radius_km", 25)
    top_n = get_prototype_config("stage1_broadcast_top_n", 5)
    response_timeout = get_prototype_config("stage1_response_timeout_seconds", 120)

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "insert into journeys (patient_id, current_stage, current_status) "
                "values (%s, 'STAGE1', 'AT_HOME') returning journey_id",
                (patient_id,),
            )
            journey_id = cur.fetchone()["journey_id"]
            assert_journey_transition("AT_HOME", "REQUESTING_HOSPITAL")

            cur.execute(
                """
                insert into patient_requests
                    (journey_id, patient_id, requester_user_id_optional, requester_role_optional,
                     urgency, location_lat, location_lon, symptom_summary, requirements_snapshot,
                     status, expires_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED', %s)
                returning id, created_at
                """,
                (
                    journey_id, patient_id,
                    body.get("requester_user_id_optional"), body.get("requester_role_optional"),
                    urgency, location_lat, location_lon, symptom_summary,
                    _json(requirements),
                    datetime.now(timezone.utc) + timedelta(seconds=response_timeout),
                ),
            )
            req_row = cur.fetchone()
            request_id = req_row["id"]

            cur.execute(
                "update journeys set stage1_request_id = %s, current_status = 'REQUESTING_HOSPITAL' where journey_id = %s",
                (request_id, journey_id),
            )

            cur.execute("select id, name, latitude, longitude from hospitals")
            hospitals = cur.fetchall()

            mandatory_types = {r["requirement_type"] for r in requirements if r.get("mandatory", True)}
            candidates = []
            for h in hospitals:
                if _distance_km(location_lat, location_lon, h["latitude"], h["longitude"]) > radius_km:
                    continue
                cur.execute("select capability from hospital_capabilities where hospital_id = %s", (h["id"],))
                caps = {r["capability"] for r in cur.fetchall()}
                if not mandatory_types.issubset(caps):
                    continue
                route = get_travel_estimate(location_lat, location_lon, h["latitude"], h["longitude"])
                candidates.append((h, route))

            candidates.sort(key=lambda c: (c[1].travel_seconds is None, c[1].travel_seconds or 0))
            broadcast_set = candidates[:top_n]

            for h, route in broadcast_set:
                cur.execute(
                    """
                    insert into patient_request_responses
                        (request_id, hospital_id, status, expires_at, travel_seconds_optional)
                    values (%s, %s, 'PENDING', %s, %s)
                    """,
                    (
                        request_id, h["id"],
                        datetime.now(timezone.utc) + timedelta(seconds=response_timeout),
                        route.travel_seconds,
                    ),
                )

            new_status = "BROADCASTING" if broadcast_set else "NO_MATCH"
            assert_stage1_request_transition("SUBMITTED", new_status)
            cur.execute("update patient_requests set status = %s where id = %s", (new_status, request_id))
    except psycopg2.errors.UniqueViolation:
        return jsonify({
            "error": "ACTIVE_REQUEST_EXISTS",
            "detail": "This patient already has an active request in progress. Cancel it first, or wait for it to resolve.",
        }), 409

    record_audit_event(
        body.get("requester_user_id_optional"), body.get("requester_role_optional"),
        "PATIENT_REQUEST_CREATED", "patient_request", request_id,
        {"broadcast_count": len(broadcast_set)},
    )

    return jsonify({
        "request_id": request_id,
        "journey_id": journey_id,
        "status": new_status,
        "broadcast_hospitals": [h["id"] for h, _ in broadcast_set],
        "created_at": req_row["created_at"].isoformat(),
    }), 201


@bp.get("/patient-requests/<request_id>")
def get_patient_request(request_id):
    with get_cursor() as cur:
        cur.execute("select * from patient_requests where id = %s", (request_id,))
        req = cur.fetchone()
        if req is None:
            return jsonify({"error": "NOT_FOUND"}), 404
        cur.execute(
            """
            select prr.*, h.name as hospital_name from patient_request_responses prr
            join hospitals h on h.id = prr.hospital_id
            where prr.request_id = %s
            """,
            (request_id,),
        )
        responses = cur.fetchall()

    result = dict(req)
    result["created_at"] = result["created_at"].isoformat()
    for f in ("expires_at", "selection_expires_at", "confirmation_expires_at"):
        if result.get(f):
            result[f] = result[f].isoformat()
    result["responses"] = []
    for r in responses:
        rd = dict(r)
        if rd.get("responded_at"):
            rd["responded_at"] = rd["responded_at"].isoformat()
        if rd.get("expires_at"):
            rd["expires_at"] = rd["expires_at"].isoformat()
        rd["updated_at"] = rd["updated_at"].isoformat()
        rd["created_at"] = rd["created_at"].isoformat()
        result["responses"].append(rd)
    return jsonify(result), 200


@bp.get("/hospitals/<hospital_id>/patient-request-responses")
def list_hospital_request_responses(hospital_id):
    with get_cursor() as cur:
        cur.execute(
            """
            select prr.*, pr.symptom_summary, pr.urgency, pr.status as request_status, pr.location_lat, pr.location_lon
            from patient_request_responses prr
            join patient_requests pr on pr.id = prr.request_id
            where prr.hospital_id = %s
            order by prr.created_at desc
            limit 50
            """,
            (hospital_id,),
        )
        rows = cur.fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat()
        d["updated_at"] = d["updated_at"].isoformat()
        if d.get("responded_at"):
            d["responded_at"] = d["responded_at"].isoformat()
        if d.get("expires_at"):
            d["expires_at"] = d["expires_at"].isoformat()
        if d["status"] == "PENDING":
            d["location_lat"] = None
            d["location_lon"] = None
        result.append(d)
    return jsonify(result), 200


@bp.post("/patient-request-responses/<response_id>/accept")
def accept_response(response_id):
    with get_cursor(commit=True) as cur:
        cur.execute("select * from patient_request_responses where id = %s", (response_id,))
        resp = cur.fetchone()
        if resp is None:
            return jsonify({"error": "NOT_FOUND"}), 404

        cur.execute(
            "update patient_request_responses set status = 'ACCEPTED', responded_at = now() "
            "where id = %s and status = 'PENDING'",
            (response_id,),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "RESPONSE_NOT_PENDING"}), 409

        cur.execute("select status from patient_requests where id = %s", (resp["request_id"],))
        req_status = cur.fetchone()["status"]
        if req_status == "BROADCASTING":
            selection_timeout = get_prototype_config("stage1_selection_timeout_seconds", 300)
            cur.execute(
                "update patient_requests set status = 'PATIENT_SELECTING', "
                "selection_expires_at = %s where id = %s",
                (datetime.now(timezone.utc) + timedelta(seconds=selection_timeout), resp["request_id"]),
            )

    record_audit_event(None, "HOSPITAL_STAFF", "HOSPITAL_ACCEPTED_REQUEST", "patient_request_response", response_id)
    return jsonify({"status": "ACCEPTED"}), 200


@bp.post("/patient-request-responses/<response_id>/decline")
def decline_response(response_id):
    body = request.get_json(force=True) or {}
    with get_cursor(commit=True) as cur:
        cur.execute(
            "update patient_request_responses set status = 'DECLINED', responded_at = now(), "
            "response_reason = %s where id = %s and status = 'PENDING'",
            (body.get("reason"), response_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "RESPONSE_NOT_PENDING"}), 409
    return jsonify({"status": "DECLINED"}), 200


@bp.post("/patient-requests/<request_id>/select")
def select_hospital(request_id):
    body = request.get_json(force=True) or {}
    hospital_id = body.get("hospital_id")
    if not hospital_id:
        return jsonify({"error": "hospital_id is required"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("select select_hospital_for_request(%s, %s) as ok", (request_id, hospital_id))
        ok = cur.fetchone()["ok"]

    if not ok:
        return jsonify({"error": "SELECTION_FAILED", "detail": "Request not in PATIENT_SELECTING or hospital not ACCEPTED"}), 409

    record_audit_event(None, "PATIENT", "PATIENT_SELECTED_HOSPITAL", "patient_request", request_id, {"hospital_id": hospital_id})
    return jsonify({"status": "CONFIRMING"}), 200


@bp.post("/patient-request-responses/<response_id>/confirm")
def confirm_selection(response_id):
    body = request.get_json(force=True) or {}
    still_eligible = bool(body.get("still_eligible", True))

    with get_cursor(commit=True) as cur:
        cur.execute("select * from patient_request_responses where id = %s", (response_id,))
        resp = cur.fetchone()
        if resp is None:
            return jsonify({"error": "NOT_FOUND"}), 404

        cur.execute(
            "select confirm_hospital_match(%s, %s, %s) as result",
            (resp["request_id"], resp["hospital_id"], still_eligible),
        )
        result = cur.fetchone()["result"]

        if result == "MATCHED":
            cur.execute(
                "update journeys set current_status = 'MATCHED_TO_HOSPITAL_1', stage1_hospital_id = %s "
                "where stage1_request_id = %s",
                (resp["hospital_id"], resp["request_id"]),
            )

    record_audit_event(None, "HOSPITAL_STAFF", "HOSPITAL_CONFIRMED_MATCH", "patient_request", resp["request_id"], {"result": result})
    return jsonify({"status": result}), (200 if result == "MATCHED" else 409)


@bp.post("/patient-requests/<request_id>/cancel")
def cancel_request(request_id):
    with get_cursor(commit=True) as cur:
        cur.execute(
            "update patient_requests set status = 'CANCELLED' where id = %s "
            "and status not in ('MATCHED','NO_MATCH','EXPIRED','CANCELLED','CONFIRMATION_FAILED') "
            "returning id",
            (request_id,),
        )
        if cur.fetchone() is None:
            return jsonify({"error": "CANNOT_CANCEL"}), 409
        cur.execute(
            "update patient_request_responses set status = 'WITHDRAWN' "
            "where request_id = %s and status = 'PENDING'",
            (request_id,),
        )
    return jsonify({"status": "CANCELLED"}), 200


def _json(obj):
    import json

    return json.dumps(obj)