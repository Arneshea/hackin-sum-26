"""
POST /simulator/hospital-state

The network simulator is a prototype control plane, not normal
hospital authority (section 41V). It is the only route allowed to set
*any* hospital's state, and only when the caller presents the
DEMO_ADMIN_TOKEN. It goes through the exact same
`apply_hospital_state_update` database function a real hospital
adapter would use (step 2.9) — there is no simulator-only shortcut
into application memory.

This is the endpoint the "Hospital A ICU 2 -> 0" live demo (section
28 / 45) drives.
"""

import uuid

from flask import Blueprint, jsonify, request, current_app

from app.services.db import get_cursor, record_audit_event

bp = Blueprint("simulator", __name__)


def _authorized(req) -> bool:
    token = req.headers.get("X-Demo-Admin-Token", "")
    return token and token == current_app.config["DEMO_ADMIN_TOKEN"]


@bp.post("/simulator/hospital-state")
def set_hospital_state():
    if not _authorized(request):
        return jsonify({"error": "UNAUTHORIZED", "detail": "Missing/invalid X-Demo-Admin-Token"}), 403

    body = request.get_json(force=True) or {}
    hospital_id = body.get("hospital_id")
    resource_type = body.get("resource_type")
    measurement_type = body.get("measurement_type")
    status = body.get("status")
    available_count = body.get("available_count_optional")
    total_count = body.get("total_count_optional")
    source_event_id = body.get("source_event_id") or str(uuid.uuid4())

    required = [hospital_id, resource_type, measurement_type, status]
    if any(v is None for v in required):
        return jsonify({"error": "hospital_id, resource_type, measurement_type, status are required"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute(
            "select * from apply_hospital_state_update(%s, %s, %s, %s, %s, %s, 'SIMULATOR', %s)",
            (hospital_id, resource_type, measurement_type, status, available_count, total_count, source_event_id),
        )
        result = cur.fetchone()

    record_audit_event(
        None, "NETWORK_ADMIN", "STATE_UPDATED", "hospital_state", hospital_id,
        {"resource_type": resource_type, "status": status, "available_count": available_count, "version": result["new_version"]},
    )

    return jsonify({
        "applied": result["applied"],
        "new_version": result["new_version"],
    }), 200


@bp.get("/simulator/network-overview")
def network_overview():
    """Admin dashboard: every hospital's current state at a glance."""
    if not _authorized(request):
        return jsonify({"error": "UNAUTHORIZED"}), 403

    with get_cursor() as cur:
        cur.execute(
            """
            select h.id as hospital_id, h.name, hs.resource_type, hs.status,
                   hs.available_count_optional, hs.total_count_optional, hs.updated_at, hs.version
            from hospitals h
            left join hospital_state hs on hs.hospital_id = h.id
            order by h.name, hs.resource_type
            """
        )
        rows = cur.fetchall()

    from app.referral_engine.freshness import freshness_category

    result = []
    for r in rows:
        d = dict(r)
        if d.get("updated_at"):
            d["freshness"] = freshness_category(r["updated_at"])
            d["updated_at"] = d["updated_at"].isoformat()
        result.append(d)
    return jsonify(result), 200
