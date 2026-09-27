"""
State freshness (step 2.7 / step 6.4). Thresholds are prototype
configuration, not medical standards, and live in `prototype_config`
under `stale_data_threshold_seconds`.
"""

from datetime import datetime, timezone

from app.services.db import get_prototype_config


def freshness_category(updated_at: datetime) -> str:
    if updated_at is None:
        return "UNKNOWN"

    thresholds = get_prototype_config(
        "stale_data_threshold_seconds",
        {"current": 60, "recent": 300, "stale": 1800},
    )

    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_seconds = (now - updated_at).total_seconds()

    if age_seconds <= thresholds["current"]:
        return "CURRENT"
    if age_seconds <= thresholds["recent"]:
        return "RECENT"
    if age_seconds <= thresholds["stale"]:
        return "STALE"
    return "UNKNOWN"


def freshness_score(category: str) -> float:
    """0..1 score used as a ranking factor (step 6.5 item 5)."""
    return {"CURRENT": 1.0, "RECENT": 0.6, "STALE": 0.2, "UNKNOWN": 0.0}.get(category, 0.0)
