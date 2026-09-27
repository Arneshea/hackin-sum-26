"""
Flask application factory (step 3.1). Configuration is kept separate
from route definitions; blueprints stay small (step 3.2) and match
the prototype's actual functionality rather than anticipating every
future endpoint.
"""

import threading

from flask import Flask
from flask_cors import CORS

from app.config import get_config
from app.triage import model as triage_model


def create_app():
    app = Flask(__name__)
    cfg = get_config()
    app.config.from_object(cfg)

    CORS(app, origins=cfg.CORS_ORIGINS, supports_credentials=True)

    # Warm the triage transformer in a background thread so the app
    # can start serving non-triage routes (patient creation, hospitals,
    # etc.) immediately.  /ready will report not-ready until the model
    # finishes loading.
    threading.Thread(target=triage_model.warm_up, daemon=True).start()

    from app.routes.health import bp as health_bp
    from app.routes.hospitals import bp as hospitals_bp
    from app.routes.patients import bp as patients_bp
    from app.routes.patient_requests import bp as patient_requests_bp
    from app.routes.referrals import bp as referrals_bp
    from app.routes.transfers import bp as transfers_bp
    from app.routes.simulator import bp as simulator_bp
    from app.routes.journeys import bp as journeys_bp
    from app.routes.emergency import bp as emergency_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(hospitals_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(patient_requests_bp)
    app.register_blueprint(referrals_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(simulator_bp)
    app.register_blueprint(journeys_bp)
    app.register_blueprint(emergency_bp)

    return app
