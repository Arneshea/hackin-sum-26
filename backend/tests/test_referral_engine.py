"""
Unit tests for the referral engine (step 22.1). These test pure logic
(eligibility.py, ranking.py, freshness.py) without touching the
database or network — no Supabase/OSRM/HF connection needed to run
these.
"""

from datetime import datetime, timedelta, timezone

from app.referral_engine.eligibility import CandidateSnapshot, evaluate_candidate
from app.referral_engine.ranking import RankingFactors, rank_candidates
from app.referral_engine.freshness import freshness_category


def _state_row(measurement_type, status, updated_at, available=None, total=None, version=1):
    return {
        "measurement_type": measurement_type,
        "status": status,
        "available_count_optional": available,
        "total_count_optional": total,
        "updated_at": updated_at,
        "version": version,
    }


NOW = datetime.now(timezone.utc)


def test_icu_unavailable_is_rejected():
    snapshot = CandidateSnapshot(
        hospital_id="B",
        capabilities={"ICU"},
        state_by_resource={"ICU": _state_row("COUNT", "UNAVAILABLE", NOW, available=0, total=8)},
    )
    result = evaluate_candidate(snapshot, [{"requirement_type": "ICU", "mandatory": True}])
    assert result.eligible is False
    assert result.rejection_reason == "ICU_UNAVAILABLE"


def test_no_icu_capability_is_rejected():
    snapshot = CandidateSnapshot(hospital_id="X", capabilities=set(), state_by_resource={})
    result = evaluate_candidate(snapshot, [{"requirement_type": "ICU", "mandatory": True}])
    assert result.eligible is False
    assert result.rejection_reason == "NO_ICU_CAPABILITY"


def test_all_mandatory_requirements_available_is_eligible():
    snapshot = CandidateSnapshot(
        hospital_id="A",
        capabilities={"ICU", "NEUROLOGY"},
        state_by_resource={
            "ICU": _state_row("COUNT", "AVAILABLE", NOW, available=2, total=10),
            "NEUROLOGY": _state_row("PERSONNEL_AVAILABILITY", "AVAILABLE", NOW),
        },
    )
    result = evaluate_candidate(snapshot, [
        {"requirement_type": "ICU", "mandatory": True},
        {"requirement_type": "NEUROLOGY", "mandatory": True},
    ])
    assert result.eligible is True


def test_stale_data_causes_rejection_for_mandatory_requirement():
    stale_time = NOW - timedelta(hours=1)
    snapshot = CandidateSnapshot(
        hospital_id="D",
        capabilities={"ICU"},
        state_by_resource={"ICU": _state_row("COUNT", "AVAILABLE", stale_time, available=3, total=10)},
    )
    result = evaluate_candidate(snapshot, [{"requirement_type": "ICU", "mandatory": True}])
    assert result.eligible is False
    assert "STALE" in result.rejection_reason or "UNKNOWN" in freshness_category(stale_time)


def test_no_feasible_hospitals_yields_empty_eligible_list():
    snapshots = [
        CandidateSnapshot(hospital_id="B", capabilities={"ICU"},
                           state_by_resource={"ICU": _state_row("COUNT", "UNAVAILABLE", NOW, available=0, total=8)}),
    ]
    results = [evaluate_candidate(s, [{"requirement_type": "ICU", "mandatory": True}]) for s in snapshots]
    assert all(r.eligible is False for r in results)


def test_ranking_prefers_shorter_travel_time_all_else_equal():
    candidates = [
        RankingFactors(hospital_id="far", travel_seconds=1200, resource_headroom=0.5, specialist_available=1.0, freshness=1.0),
        RankingFactors(hospital_id="near", travel_seconds=300, resource_headroom=0.5, specialist_available=1.0, freshness=1.0),
    ]
    ranked = rank_candidates(candidates)
    assert ranked[0].hospital_id == "near"


def test_ranking_deterministic_tie_break_on_hospital_id():
    candidates = [
        RankingFactors(hospital_id="zzz", travel_seconds=300, resource_headroom=0.5, specialist_available=1.0, freshness=1.0),
        RankingFactors(hospital_id="aaa", travel_seconds=300, resource_headroom=0.5, specialist_available=1.0, freshness=1.0),
    ]
    ranked = rank_candidates(candidates)
    # identical factors -> identical score -> tie-break falls through to hospital_id
    assert ranked[0].hospital_id == "aaa"
