from flagcore import bucket


def test_hash_input_is_user_colon_flag():
    # crc32(b"ben@example.com:search-v2") % 100 == 67 -> out at 50
    assert bucket("ben@example.com", "search-v2", 50) is False
    # crc32(b"eli@example.com:promo-banner") % 100 == 32 -> in at 50
    assert bucket("eli@example.com", "promo-banner", 50) is True


def test_boundary_is_strictly_less_than():
    # crc32(b"cody@example.com:dark-mode") % 100 == 37
    assert bucket("cody@example.com", "dark-mode", 37) is False
    assert bucket("cody@example.com", "dark-mode", 38) is True


def test_zero_percent_enrolls_nobody():
    assert bucket("dana@mail.net", "perf-cache", 0) is False
    assert bucket("user-4821", "fast-reco", 0) is False


def test_hundred_percent_enrolls_everybody():
    assert bucket("lena@mail.net", "new-nav", 100) is True
    assert bucket("ana@example.com", "new-checkout", 100) is True


def test_per_flag_independence():
    # crc32(b"ana@example.com:new-checkout") % 100 == 79; ...:new-nav == 1
    assert bucket("ana@example.com", "new-checkout", 50) is False
    assert bucket("ana@example.com", "new-nav", 50) is True


def test_corp_users_always_in_beta_flags():
    assert bucket("dev@corp.example", "beta-newui", 0) is True
    assert bucket("ops@corp.example", "beta-dashboard", 0) is True


def test_corp_users_bucket_normally_on_other_flags():
    assert bucket("dev@corp.example", "perf-cache", 0) is False
    # crc32(b"dev@corp.example:perf-cache") % 100 == 73
    assert bucket("dev@corp.example", "perf-cache", 73) is False
    assert bucket("dev@corp.example", "perf-cache", 74) is True


def test_non_corp_users_bucket_normally_on_beta_flags():
    # crc32(b"ana@example.com:beta-newui") % 100 == 68
    assert bucket("ana@example.com", "beta-newui", 68) is False
    assert bucket("ana@example.com", "beta-newui", 69) is True
