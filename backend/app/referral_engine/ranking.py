"""
Ranking (step 6.5-6.8, section 41W "Final MVP Set").

MVP ranking factors, in the exact final-MVP set:
  1. travel time
  2. relevant resource headroom (ICU/etc. availability ratio)
  3. relevant specialist availability
  4. state freshness

`current operational load` from the section-41W list is deliberately
folded into "resource headroom" rather than scored twice — section
6.5 requires operational load's exact definition to be documented if
used, and the clearest non-duplicative definition available from the
data this prototype actually has is headroom (available/total) on the
mandatory count-type resource. This is documented in
docs/DATA_MODEL.md. No star ratings, predicted wait time, or future
bed prediction are included (explicitly excluded by step 6.5 / 41W).

All factors are normalized to 0..1 before combining. Weights are a
versioned config object (`ranking_weights_v1`); every ranking run
records which policy_version produced it (section 0.9 / step 6.6).
"""

from dataclasses import dataclass, field
from typing import Optional

from app.referral_engine.freshness import freshness_score
from app.services.db import get_prototype_config
from app.config import get_config


@dataclass
class RankingFactors:
    hospital_id: str
    travel_seconds: Optional[float]
    resource_headroom: Optional[float]  # 0..1, e.g. ICU available/total
    specialist_available: Optional[float]  # 0/1 (or 0.5 for ON_CALL)
    freshness: float  # 0..1
    routing_source: str = "UNKNOWN"


@dataclass
class RankedCandidate:
    hospital_id: str
    score: float
    factors: dict
    explanation_lines: list = field(default_factory=list)


def _normalize_travel_time(travel_seconds: Optional[float], all_travel_seconds: list[float]) -> float:
    if travel_seconds is None or not all_travel_seconds:
        return 0.0
    max_t = max(all_travel_seconds) or 1.0
    min_t = min(all_travel_seconds)
    if max_t == min_t:
        return 1.0
    # shorter travel time -> higher normalized score
    return 1.0 - ((travel_seconds - min_t) / (max_t - min_t))


def rank_candidates(candidates: list[RankingFactors]) -> list[RankedCandidate]:
    weights = get_prototype_config(
        "ranking_weights_v1",
        {"travel_time": 0.35, "resource_headroom": 0.30, "specialist_availability": 0.20, "state_freshness": 0.15},
    )
    tie_breakers = get_prototype_config("ranking_tie_breakers", ["freshness", "travel_time", "hospital_id"])
    policy_version = get_config().RANKING_POLICY_VERSION

    all_travel = [c.travel_seconds for c in candidates if c.travel_seconds is not None]

    ranked = []
    for c in candidates:
        norm_travel = _normalize_travel_time(c.travel_seconds, all_travel)
        norm_headroom = c.resource_headroom if c.resource_headroom is not None else 0.0
        norm_specialist = c.specialist_available if c.specialist_available is not None else 0.0
        norm_freshness = c.freshness

        score = (
            weights["travel_time"] * norm_travel
            + weights["resource_headroom"] * norm_headroom
            + weights["specialist_availability"] * norm_specialist
            + weights["state_freshness"] * norm_freshness
        )

        factors = {
            "travel_time_normalized": round(norm_travel, 4),
            "travel_seconds": c.travel_seconds,
            "routing_source": c.routing_source,
            "resource_headroom": round(norm_headroom, 4),
            "specialist_available": norm_specialist,
            "freshness": round(norm_freshness, 4),
            "policy_version": policy_version,
        }
        ranked.append(RankedCandidate(hospital_id=c.hospital_id, score=round(score, 6), factors=factors))

    # Deterministic tie-breaking (step 6.7): sort by score desc, then
    # by the configured tie-breaker sequence, never by incidental row order.
    def sort_key(rc: RankedCandidate):
        keys = [-rc.score]
        for tb in tie_breakers:
            if tb == "freshness":
                keys.append(-rc.factors["freshness"])
            elif tb == "travel_time":
                keys.append(rc.factors["travel_seconds"] if rc.factors["travel_seconds"] is not None else float("inf"))
            elif tb == "hospital_id":
                keys.append(rc.hospital_id)
        return tuple(keys)

    ranked.sort(key=sort_key)
    return ranked
