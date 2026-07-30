import pytest
from orderflow import advance, InvalidTransition


def test_cancel_reachable_only_from_pending_or_hold():
    assert advance({"state": "pending"}, "cancelled")["state"] == "cancelled"
    assert advance({"state": "on_hold"}, "cancelled")["state"] == "cancelled"
    with pytest.raises(InvalidTransition):
        advance({"state": "paid"}, "cancelled")


def test_refund_reachable_only_from_returned():
    assert advance({"state": "returned"}, "refunded")["state"] == "refunded"
    with pytest.raises(InvalidTransition):
        advance({"state": "shipped"}, "refunded")
    with pytest.raises(InvalidTransition):
        advance({"state": "paid"}, "refunded")


def test_hold_releases_back_to_pending_not_paid():
    assert advance({"state": "on_hold"}, "pending")["state"] == "pending"
    with pytest.raises(InvalidTransition):
        advance({"state": "on_hold"}, "paid")


def test_returned_order_cannot_be_cancelled():
    with pytest.raises(InvalidTransition):
        advance({"state": "returned"}, "cancelled")


def test_terminal_states_stay_terminal():
    for terminal in ("cancelled", "refunded"):
        for target in ("pending", "paid", "on_hold", "shipped", "returned",
                       "cancelled", "refunded"):
            if target == terminal:
                continue
            with pytest.raises(InvalidTransition):
                advance({"state": terminal}, target)


def test_current_state_matched_case_insensitively():
    assert advance({"state": "PAID"}, "shipped")["state"] == "shipped"
    assert advance({"state": "On_Hold"}, "pending")["state"] == "pending"


def test_target_matched_case_insensitively_and_stored_lowercase():
    assert advance({"state": "pending"}, "PAID")["state"] == "paid"
    assert advance({"state": "Shipped"}, "Returned")["state"] == "returned"
