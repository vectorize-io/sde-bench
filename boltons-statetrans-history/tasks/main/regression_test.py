import pytest
from orderflow import advance, InvalidTransition


def test_charged_order_cannot_go_straight_to_cancelled():
    with pytest.raises(InvalidTransition):
        advance({"state": "paid"}, "cancelled")


def test_charged_order_can_be_parked_on_hold():
    assert advance({"state": "paid"}, "on_hold")["state"] == "on_hold"
