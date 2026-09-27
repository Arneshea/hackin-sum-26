"""
GET   /hospitals
GET   /hospitals/<id>
GET   /hospitals/<id>/state
PATCH /hospitals/<id>/state   -- restricted; see section 41V. Ordinary
                                  hospital-staff writes to their own
                                  hospital's state should go through
                                  Supabase directly under RLS, or an
                                  authenticated hospital-staff route
                                  (not implemented in this prototype
                                  pass — only the demo simulator writes
                                  state here, via /simulator/*).
"""

from flask import Blueprint, jsonify

from app.services.db import get_cursor

bp = Blueprint("hospitals", __name__)


@bp.get("/hospitals")
def list_hospitals():
    with get_cursor() as cur:
        cur.execute("select id, name, address, latitude, longitude, type, is_synthetic from hospitals order by name")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows]), 200


@bp.get("/hospitals/<hospital_id>")
def get_hospital(hospital_id):
    with get_cursor() as cur:
        cur.execute("select * from hospitals where id = %s", (hospital_id,))
        hosp = cur.fetchone()
        if hosp is None:
            return jsonify({"error": "NOT_FOUND"}), 404
        cur.execute("select capability from hospital_capabilities where hospital_id = %s", (hospital_id,))
        capabilities = [r["capability"] for r in cur.fetchall()]
    result = dict(hosp)
    result["capabilities"] = capabilities
    return jsonify(result), 200


@bp.get("/hospitals/<hospital_id>/state")
def get_hospital_state(hospital_id):
    with get_cursor() as cur:
        cur.execute(
            "select resource_type, measurement_type, status, available_count_optional, "
            "total_count_optional, updated_at, source, version from hospital_state "
            "where hospital_id = %s",
            (hospital_id,),
        )
        rows = cur.fetchall()

    from app.referral_engine.freshness import freshness_category

    result = []
    for r in rows:
        d = dict(r)
        d["updated_at"] = d["updated_at"].isoformat()
        d["freshness"] = freshness_category(r["updated_at"])
        result.append(d)
    return jsonify(result), 200
