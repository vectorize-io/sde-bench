from flagcore import bucket


def test_membership_is_independent_per_flag():
    a = bucket("ana@example.com", "new-checkout", 50)
    b = bucket("ana@example.com", "new-nav", 50)
    assert a != b
    assert b is True
