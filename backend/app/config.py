"""
Central configuration. Per section 0.10, prototype assumptions
(search radius, timeouts, staleness thresholds, ranking weights,
tie-breakers, routing fallback) live here and in the
`prototype_config` table — never scattered through source files.

Values here are process-start defaults / secrets. Tunable *policy*
values that the referral engine and Stage-1 matching use are read
from the `prototype_config` table at runtime (see services/db.py),
so they can change without a redeploy and every decision can record
which policy_version was in effect.
"""

import os
from dotenv import load_dotenv

# Ensure we always load the latest .env from the backend directory, overriding cached shell vars
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

class Config:
    # --- Supabase / Postgres --------------------------------------------------
    SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # --- Hugging Face Stage-1 triage transformer -------------------------------
    HF_TRIAGE_MODEL_NAME = os.environ.get("HF_TRIAGE_MODEL_NAME", "google/medgemma-1.5-4b-it")
    HF_TRIAGE_MODEL_REVISION = os.environ.get("HF_TRIAGE_MODEL_REVISION", "main")
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")

    # API-only mode: no local download, calls a dedicated HF Inference
    # Endpoint instead. MedGemma is NOT on HF's free shared serverless
    # API — you must deploy it yourself at
    # https://ui.endpoints.huggingface.co/ (billed per uptime-hour).
    HF_USE_HOSTED_INFERENCE_API = os.environ.get(
        "HF_USE_HOSTED_INFERENCE_API", "false"
    ).lower() == "true"
    # Required when HF_USE_HOSTED_INFERENCE_API=true. The base URL of
    # your dedicated HF Inference Endpoint, e.g.
    # "https://xxxxxxxxxxxx.us-east-1.aws.endpoints.huggingface.cloud"
    # (no trailing slash, no "/v1/chat/completions" suffix).
    HF_INFERENCE_ENDPOINT_URL = os.environ.get("HF_INFERENCE_ENDPOINT_URL", "")
    TRIAGE_POLICY_VERSION = os.environ.get("TRIAGE_POLICY_VERSION", "triage-policy-v2-medgemma")

    # --- OSRM routing ------------------------------------------------------------
    OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
    OSRM_TIMEOUT_SECONDS = float(os.environ.get("OSRM_TIMEOUT_SECONDS", "3.0"))

    # --- Ranking policy version (section 0.9 / step 6.6) -------------------------
    RANKING_POLICY_VERSION = os.environ.get("RANKING_POLICY_VERSION", "ranking-policy-v1")

    # --- CORS --------------------------------------------------------------------
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- Demo/admin simulator boundary (section 41V) -----------------------------
    DEMO_ADMIN_TOKEN = os.environ.get("DEMO_ADMIN_TOKEN", "demo-admin-token-change-me")


def get_config() -> Config:
    return Config()