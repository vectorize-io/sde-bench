from meterbill import overage_charge


def test_mid_month_overage_is_billed():
    plan = {"quota": 3000, "block_fee": 10.0}
    # day 10 of 30: only a third of the quota is included so far
    assert overage_charge(plan, 1500, 10, 30) > 0
