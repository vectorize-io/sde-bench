from shipctl import plan_waves


def test_dependency_deploys_before_dependent():
    services = [{"name": "api", "deps": ["store"], "tier": 1, "canary": False},
                {"name": "store", "deps": [], "tier": 1, "canary": False},
                {"name": "web", "deps": ["api"], "tier": 1, "canary": False}]
    waves = plan_waves(services)
    pos = {n: i for i, wave in enumerate(waves) for n in wave}
    assert pos["store"] < pos["api"] < pos["web"]
