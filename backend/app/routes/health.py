"""
GET /health  -> process is running (step 3.3 / section 28A)
GET /ready   -> required prototype dependencies are actually ready

Never report /ready as healthy if the triage model or database is
unavailable (section 41S: "Do not report the service as ready if a
required dependency is unavailable.").
"""

from flask import Blueprint, jsonify

from app.services.db import db_reachable
from app.triage import model as triage_model

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@bp.get("/ready")
def ready():
    db_ok = db_reachable()
    model_ok = triage_model.is_ready()
    checks = {
        "database_reachable": db_ok,
        "triage_model_loaded": model_ok,
        "triage_model_metrics": triage_model.get_load_metrics(),
    }
    overall_ready = db_ok and model_ok
    return jsonify({"ready": overall_ready, "checks": checks}), (200 if overall_ready else 503)
