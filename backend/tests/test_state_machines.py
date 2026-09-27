import pytest

from app.utils.state_machines import (
    IllegalTransitionError,
    assert_stage2_referral_transition,
    assert_transfer_transition,
    assert_journey_transition,
)


def test_pending_to_accepted_valid():
    # modeled via referral response semantics is boolean elsewhere;
    # here we test the referral-level equivalent PENDING_ACCEPTANCE -> ACCEPTED
    assert_stage2_referral_transition("PENDING_ACCEPTANCE", "ACCEPTED")


def test_pending_to_declined_all_valid_via_broadcasting():
    assert_stage2_referral_transition("BROADCASTING", "DECLINED_ALL")


def test_accepted_to_transfer_initiated_valid():
    assert_transfer_transition("ACCEPTED", "TRANSFER_INITIATED")


def test_transfer_to_received_valid():
    assert_transfer_transition("EN_ROUTE", "PATIENT_RECEIVED")


def test_completed_to_accepted_invalid():
    with pytest.raises(IllegalTransitionError):
        assert_transfer_transition("HANDOFF_COMPLETED", "ACCEPTED")


def test_journey_cannot_skip_arrival_states():
    with pytest.raises(IllegalTransitionError):
        assert_journey_transition("MATCHED_TO_HOSPITAL_1", "UNDER_CARE")
