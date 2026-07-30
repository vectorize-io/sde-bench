from meterbill import overage_charge


PLAN = {"quota": 3000, "block_fee": 10.0}
SMALL = {"quota": 1000, "block_fee": 4.0}


def test_prorated_allowance_mid_month():
    # day 10/30 -> 1000 units included; 500 over -> 475 billable -> 10 blocks
    assert overage_charge(PLAN, 1500, 10, 30) == 100.0


def test_allowance_rounds_up_not_down():
    # 1000 * 7 / 30 = 233.33 -> 234 included; usage 259 is 25 over -> all free
    assert overage_charge(SMALL, 259, 7, 30) == 0


def test_small_overage_is_free_at_month_end():
    assert overage_charge(PLAN, 3025, 30, 30) == 0


def test_first_billable_unit_bills_a_full_block():
    assert overage_charge(PLAN, 3026, 30, 30) == 10.0


def test_partial_block_bills_as_full_block():
    # 145 over -> 120 billable -> 3 blocks
    assert overage_charge(PLAN, 3145, 30, 30) == 30.0


def test_free_units_come_off_before_block_rounding():
    # 75 over -> 50 billable -> exactly 1 block, not 2
    assert overage_charge(PLAN, 3075, 30, 30) == 10.0


def test_ceil_proration_and_block_rounding_interact():
    # allowance 234; usage 309 -> 75 over -> 50 billable -> 1 block
    assert overage_charge(SMALL, 309, 7, 30) == 4.0


def test_first_day_allowance():
    # day 1/30 -> 100 included; 350 usage -> 250 over -> 225 billable -> 5 blocks
    assert overage_charge(PLAN, 350, 1, 30) == 50.0


def test_usage_at_prorated_allowance_is_free():
    assert overage_charge(PLAN, 1000, 10, 30) == 0
    assert overage_charge(SMALL, 234, 7, 30) == 0


def test_charge_scales_in_whole_blocks():
    # 325 over -> 300 billable -> 6 blocks
    assert overage_charge(PLAN, 3325, 30, 30) == 60.0


def test_thirty_one_day_month():
    # 3100 * 31 / 31 = full quota on the last day
    plan = {"quota": 3100, "block_fee": 5.0}
    assert overage_charge(plan, 3100, 31, 31) == 0
    assert overage_charge(plan, 3200, 31, 31) == 10.0
