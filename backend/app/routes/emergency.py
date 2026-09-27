"""
POST /emergency-dispatch

The emergency button on the patient screen (new requirement): a
single tap dispatches the nearest capable hospital's ambulance
immediately, with NO triage questions, NO Stage-1 broadcast/accept
negotiation, and NO patient selection step. This is deliberately a
different — and simpler — code path than patient_requests.py:

  Stage-1 matching (patient_requests.py): broadcast -> hospitals
  decide -> patient picks -> hospital confirms. Takes time; assumes
  the patient can wait through a negotiation.

  Emergency dispatch (this file): skip straight to "send the nearest
  ambulance," full stop. If nothing is found within the search radius,
  say so immediately and clearly rather than silently retrying — a
  person hitting this button needs an unambiguous answer fast.

This does not replace calling local emergency services — see the
warning text returned in the response and shown in the UI.
"""

import math
import uuid

from flask import Blueprint, jsonify, request

from app.services.db import get_cursor, get_prototype_config, record_audit_event
from app.services.routing import get_travel_estimate
from app.utils.state_machines import assert_journey_transition

bp = Blueprint("emergency", __name__)


def _distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@bp.post("/emergency-dispatch")
def emergency_dispatch():
    body = request.get_json(force=True) or {}
    patient_id = body.get("patient_id")
    location_lat = body.get("location_lat")
    location_lon = body.get("location_lon")

    if location_lat is None or location_lon is None:
        return jsonify({"error": "location_lat and location_lon are required"}), 400

    radius_km = get_prototype_config("candidate_search_radius_km", 25)

    with get_cursor(commit=True) as cur:
        # An emergency button press must never be blocked on "create a
        # patient record first" — auto-create an anonymous placeholder
        # if none was supplied, and let it be reconciled with a real
        # identity later (out of scope for this pass).
        if not patient_id:
            cur.execute(
                "insert into patients (display_name) values ('Emergency (unidentified)') returning id"
            )
            patient_id = cur.fetchone()["id"]

        cur.execute(
            "insert into journeys (patient_id, current_stage, current_status) "
            "values (%s, 'STAGE1', 'AT_HOME') returning journey_id",
            (patient_id,),
        )
        journey_id = cur.fetchone()["journey_id"]

        # Nearest hospital with EMERGENCY capability, by straight
        # candidate scan — deliberately not run through the referral
        # engine's ranking (that engine answers "which hospital is the
        # best-suited destination"; this question is simply "which
        # ambulance is closest," step 4.14's spirit but simplified
        # further given there is no negotiation here at all).
        cur.execute("select id, name, latitude, longitude from hospitals")
        hospitals = cur.fetchall()

        candidates = []
        for h in hospitals:
            if _distance_km(location_lat, location_lon, h["latitude"], h["longitude"]) > radius_km:
                continue
            cur.execute("select 1 from hospital_capabilities where hospital_id = %s and capability = 'EMERGENCY'", (h["id"],))
            if cur.fetchone() is None:
                continue
            route = get_travel_estimate(location_lat, location_lon, h["latitude"], h["longitude"])
            candidates.append((h, route))

        candidates.sort(key=lambda c: (c[1].travel_seconds is None, c[1].travel_seconds or 0))

        if not candidates:
            cur.execute(
                """
                insert into emergency_dispatches
                    (journey_id, patient_id, location_lat, location_lon, status)
                values (%s, %s, %s, %s, 'NO_HOSPITAL_FOUND')
                returning id
                """,
                (journey_id, patient_id, location_lat, location_lon),
            )
            dispatch_id = cur.fetchone()["id"]
            record_audit_event(None, None, "EMERGENCY_DISPATCH_NO_HOSPITAL_FOUND", "journey", journey_id)
            return jsonify({
                "status": "NO_HOSPITAL_FOUND",
                "dispatch_id": dispatch_id,
                "journey_id": journey_id,
                "warning": "No hospital with emergency capability found nearby. Call your local emergency number immediately.",
            }), 200

        hospital, route = candidates[0]

        # Emergency dispatch skips REQUESTING_HOSPITAL / MATCHED_TO_HOSPITAL_1
        # entirely (there is no negotiation to wait for) and goes
        # straight to "an ambulance is now en route."
        assert_journey_transition("AT_HOME", "EN_ROUTE_TO_HOSPITAL_1")
        cur.execute(
            "update journeys set current_status = 'EN_ROUTE_TO_HOSPITAL_1', stage1_hospital_id = %s where journey_id = %s",
            (hospital["id"], journey_id),
        )

        cur.execute(
            """
            insert into emergency_dispatches
                (journey_id, patient_id, location_lat, location_lon,
                 dispatched_hospital_id, routing_source, travel_seconds_optional, status)
            values (%s, %s, %s, %s, %s, %s, %s, 'DISPATCHED')
            returning id, created_at
            """,
            (journey_id, patient_id, location_lat, location_lon, hospital["id"], route.source, route.travel_seconds),
        )
        dispatch_row = cur.fetchone()

    record_audit_event(
        None, "PATIENT", "EMERGENCY_DISPATCHED", "journey", journey_id,
        {"hospital_id": hospital["id"], "travel_seconds": route.travel_seconds},
    )

    return jsonify({
        "status": "DISPATCHED",
        "dispatch_id": dispatch_row["id"],
        "journey_id": journey_id,
        "patient_id": patient_id,
        "hospital": {"id": hospital["id"], "name": hospital["name"], "latitude": hospital["latitude"], "longitude": hospital["longitude"]},
        "eta_seconds": route.travel_seconds,
        "eta_source": route.source,
        "warning": "This dispatches the nearest network-registered emergency hospital in this prototype. It does not replace calling your local emergency number.",
    }), 201
