from labelsync import merge_tags


def test_dedupe_keeps_highest_precedence_casing():
    assert merge_tags([["Prod", "Web"], ["prod", "PROD", "db"]]) == ["Prod", "Web", "db"]


def test_tombstone_suppresses_lower_precedence_sources():
    assert merge_tags([["-legacy"], ["legacy", "web"]]) == ["web"]


def test_tombstone_cannot_remove_higher_precedence_assert():
    assert merge_tags([["critical"], ["-critical", "db"]]) == ["critical", "db"]


def test_tombstone_matches_case_insensitively():
    assert merge_tags([["-Legacy"], ["legacy", "APP"]]) == ["APP"]


def test_mid_level_tombstone_only_affects_lower_sources():
    assert merge_tags([["alpha"], ["-beta"], ["beta", "gamma"]]) == ["alpha", "gamma"]


def test_tombstoned_tag_stays_out_even_when_reasserted_below():
    assert merge_tags([["ops", "-standby"], ["standby", "ops"]]) == ["ops"]


def test_unmatched_tombstones_are_silently_fine():
    assert merge_tags([["-ghost"], ["app"]]) == ["app"]
    assert merge_tags([["-a", "-b"]]) == []


def test_first_occurrence_order_is_kept():
    assert merge_tags([["b", "a"], ["c", "A"]]) == ["b", "a", "c"]


def test_case_variants_across_three_sources_collapse_to_topmost():
    assert merge_tags([["Tier:Gold"], ["tier:gold"], ["TIER:GOLD", "extra"]]) == ["Tier:Gold", "extra"]
