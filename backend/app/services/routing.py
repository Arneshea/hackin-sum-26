"""
Routing service — the only place that talks to OSRM (section 41R:
external services must be wrapped, not scattered across routes).

Failure behavior (section 21 / step 4.14): if OSRM is unreachable or
errors, this module does NOT fabricate an ETA. It returns a result
object with `travel_seconds=None` and `source="UNAVAILABLE"`, OR — if
`routing_fallback_policy` in prototype_config is set to
"GEOGRAPHIC_DISTANCE" (the default) — returns a clearly labeled
straight-line-distance estimate with `source="GEOGRAPHIC_FALLBACK"`.
Callers (candidate ranking, UI) must check `source` before treating
a travel estimate as a real routed ETA.
"""

import math
from dataclasses import dataclass
from typing import Optional

import requests

from app.config import get_config
from app.services.db import get_prototype_config


@dataclass
class RouteEstimate:
    travel_seconds: Optional[float]
    distance_meters: Optional[float]
    source: str  # "OSRM" | "GEOGRAPHIC_FALLBACK" | "UNAVAILABLE"


def _haversine_meters(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# Configurable assumption (section 0.10): used only by the geographic
# fallback to turn distance into a rough ETA. This is explicitly NOT a
# claim about real traffic conditions.
_FALLBACK_AVG_SPEED_KMH = 30.0


def get_travel_estimate(origin_lat, origin_lon, dest_lat, dest_lon) -> RouteEstimate:
    cfg = get_config()
    try:
        url = (
            f"{cfg.OSRM_BASE_URL}/route/v1/driving/"
            f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            f"?overview=false"
        )
        resp = requests.get(url, timeout=cfg.OSRM_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        route = data["routes"][0]
        return RouteEstimate(
            travel_seconds=route["duration"],
            distance_meters=route["distance"],
            source="OSRM",
        )
    except Exception:
        fallback_policy = get_prototype_config("routing_fallback_policy", "GEOGRAPHIC_DISTANCE")
        if fallback_policy != "GEOGRAPHIC_DISTANCE":
            return RouteEstimate(travel_seconds=None, distance_meters=None, source="UNAVAILABLE")

        distance_m = _haversine_meters(origin_lat, origin_lon, dest_lat, dest_lon)
        estimated_seconds = (distance_m / 1000.0) / _FALLBACK_AVG_SPEED_KMH * 3600.0
        return RouteEstimate(
            travel_seconds=estimated_seconds,
            distance_meters=distance_m,
            source="GEOGRAPHIC_FALLBACK",
        )
