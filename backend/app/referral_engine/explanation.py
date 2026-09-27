"""
Explanation generation (step 6.10). Every line here is derived from a
factor that was actually used by eligibility.py / ranking.py — never
add a line for something the engine didn't check.
"""


def explain_eligible(hospital_name: str, requirements: list[dict], factors: dict) -> list[str]:
    lines = [f"{hospital_name} recommended because:"]
    for req in requirements:
        if req.get("mandatory", True):
            lines.append(f"\u2713 {req['requirement_type']} available")

    if factors.get("travel_seconds") is not None:
        minutes = round(factors["travel_seconds"] / 60)
        suffix = "" if factors.get("routing_source") == "OSRM" else " (distance-based estimate)"
        lines.append(f"\u2713 {minutes} min estimated travel{suffix}")

    freshness_pct = factors.get("freshness")
    if freshness_pct is not None:
        lines.append(f"\u2713 State freshness score {round(freshness_pct * 100)}%")

    return lines


def explain_rejected(hospital_name: str, rejection_reason: str) -> list[str]:
    return [f"{hospital_name} not recommended: {rejection_reason.replace('_', ' ').title()}"]
