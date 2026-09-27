"""
scripts/seed_demo_data.py

Seeds/refreshes the section-28 demo scenario's hospital_state rows by
calling the running Flask API's /simulator/hospital-state endpoint —
i.e. through the same contract a real hospital adapter would use
(step 2.9), rather than writing to Postgres directly.

Run database/migrations/*.sql and database/seed/demo_seed.sql first to
create the hospitals/capabilities/resources; this script is for
resetting operational *state* to the section 28 starting point without
re-running the full SQL seed (handy between demo run-throughs).

Usage:
    python scripts/seed_demo_data.py --api-base http://localhost:8000 --token <DEMO_ADMIN_TOKEN>
"""

import argparse
import sys

import requests

HOSPITAL_A = "11111111-1111-1111-1111-111111111111"
HOSPITAL_B = "22222222-2222-2222-2222-222222222222"
HOSPITAL_C = "33333333-3333-3333-3333-333333333333"

STARTING_STATE = [
    dict(hospital_id=HOSPITAL_A, resource_type="ICU", measurement_type="COUNT", status="AVAILABLE", available_count_optional=2, total_count_optional=10),
    dict(hospital_id=HOSPITAL_B, resource_type="ICU", measurement_type="COUNT", status="UNAVAILABLE", available_count_optional=0, total_count_optional=8),
    dict(hospital_id=HOSPITAL_C, resource_type="ICU", measurement_type="COUNT", status="AVAILABLE", available_count_optional=1, total_count_optional=6),
    dict(hospital_id=HOSPITAL_A, resource_type="NEUROLOGY_SPECIALIST", measurement_type="PERSONNEL_AVAILABILITY", status="AVAILABLE"),
    dict(hospital_id=HOSPITAL_B, resource_type="NEUROLOGY_SPECIALIST", measurement_type="PERSONNEL_AVAILABILITY", status="ON_CALL"),
    dict(hospital_id=HOSPITAL_C, resource_type="NEUROLOGY_SPECIALIST", measurement_type="PERSONNEL_AVAILABILITY", status="AVAILABLE"),
    dict(hospital_id=HOSPITAL_A, resource_type="CT", measurement_type="BINARY_SERVICE", status="OPERATIONAL"),
    dict(hospital_id=HOSPITAL_B, resource_type="CT", measurement_type="BINARY_SERVICE", status="OPERATIONAL"),
    dict(hospital_id=HOSPITAL_C, resource_type="CT", measurement_type="BINARY_SERVICE", status="OPERATIONAL"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="DEMO_ADMIN_TOKEN configured on the backend")
    args = parser.parse_args()

    headers = {"X-Demo-Admin-Token": args.token}
    for i, state in enumerate(STARTING_STATE):
        state = dict(state, source_event_id=f"cli-seed-{i}")
        resp = requests.post(f"{args.api_base}/simulator/hospital-state", json=state, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"FAILED: {state} -> {resp.status_code} {resp.text}", file=sys.stderr)
            sys.exit(1)
        print(f"OK: {state['hospital_id'][:8]} {state['resource_type']} -> {state['status']} ({resp.json()})")

    print("\nDemo state reset to the section 28 starting point.")


if __name__ == "__main__":
    main()
