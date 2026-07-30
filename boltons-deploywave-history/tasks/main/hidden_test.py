from shipctl import plan_waves


def _svc(name, deps=(), tier=1, canary=False):
    return {"name": name, "deps": list(deps), "tier": tier, "canary": canary}


def test_wave_follows_the_deepest_dependency():
    services = [_svc("base"), _svc("mid", deps=["base"]),
                _svc("top", deps=["base", "mid"])]
    assert plan_waves(services) == [["base"], ["mid"], ["top"]]


def test_within_wave_most_critical_tier_first():
    services = [_svc("alpha", tier=2), _svc("mango", tier=0), _svc("zebra", tier=1)]
    assert plan_waves(services) == [["mango", "zebra", "alpha"]]


def test_tier_tie_breaks_by_name():
    services = [_svc("delta", tier=1), _svc("bravo", tier=1), _svc("echo", tier=0)]
    assert plan_waves(services) == [["echo", "bravo", "delta"]]


def test_canaries_deploy_first_despite_dependencies():
    services = [_svc("core"), _svc("api", deps=["core"]),
                _svc("zzz-probe", deps=["api"], tier=3, canary=True)]
    assert plan_waves(services) == [["zzz-probe"], ["core"], ["api"]]


def test_canary_wave_ordered_by_name():
    services = [_svc("watch", canary=True), _svc("probe", canary=True), _svc("app")]
    assert plan_waves(services) == [["probe", "watch"], ["app"]]


def test_dependency_on_a_canary_counts_as_satisfied():
    services = [_svc("edge", canary=True), _svc("api", deps=["edge"])]
    assert plan_waves(services) == [["edge"], ["api"]]


def test_no_canaries_means_no_leading_empty_wave():
    services = [_svc("a"), _svc("b", deps=["a"])]
    assert plan_waves(services) == [["a"], ["b"]]


def test_full_release_plan():
    services = [_svc("probe", deps=["gateway"], tier=3, canary=True),
                _svc("core-db", tier=0),
                _svc("cache", tier=1),
                _svc("audit", tier=3),
                _svc("gateway", deps=["core-db", "cache"], tier=0),
                _svc("worker", deps=["cache"], tier=2),
                _svc("portal", deps=["gateway"], tier=1)]
    assert plan_waves(services) == [["probe"],
                                    ["core-db", "cache", "audit"],
                                    ["gateway", "worker"],
                                    ["portal"]]
