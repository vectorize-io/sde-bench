from labelsync import merge_tags


def test_migrated_sources_merge_cleanly():
    sources = [["Env:Prod", "team-core"],
               ["env:prod", "-decommissioned", "region-eu"]]
    assert merge_tags(sources) == ["Env:Prod", "team-core", "region-eu"]
