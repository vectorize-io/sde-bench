from jobsched import next_job


def _job(id, tenant, priority, submitted_at, est_runtime):
    return {"id": id, "tenant": tenant, "priority": priority,
            "submitted_at": submitted_at, "est_runtime": est_runtime}


def test_priority_tie_prefers_shorter_job():
    q = [_job("long", "t1", 5, "2024-06-01T09:00:00", 300),
         _job("short", "t2", 5, "2024-06-01T09:05:00", 60)]
    assert next_job(q, "other")["id"] == "short"
    assert next_job(q, "t1")["id"] == "short"


def test_priority_tie_shorter_wins_three_way():
    q = [_job("a", "t1", 4, "2024-06-01T08:00:00", 500),
         _job("b", "t2", 4, "2024-06-01T08:10:00", 200),
         _job("c", "t3", 4, "2024-06-01T08:20:00", 350)]
    assert next_job(q, "other")["id"] == "b"


def test_recent_tenant_skipped_even_at_higher_priority():
    q = [_job("p", "acme", 9, "2024-06-01T09:00:00", 60),
         _job("q", "beta", 3, "2024-06-01T09:01:00", 60)]
    assert next_job(q, "acme")["id"] == "q"
    assert next_job(q, "beta")["id"] == "p"


def test_recent_tenant_skipped_even_if_shorter_and_higher():
    q = [_job("p2", "acme", 8, "2024-06-01T09:00:00", 10),
         _job("q2", "beta", 2, "2024-06-01T09:01:00", 900),
         _job("r2", "acme", 7, "2024-06-01T09:02:00", 5)]
    assert next_job(q, "acme")["id"] == "q2"


def test_recent_tenant_runs_when_alone_in_queue():
    q = [_job("x", "acme", 2, "2024-06-01T09:00:00", 60),
         _job("y", "acme", 6, "2024-06-01T09:01:00", 60)]
    assert next_job(q, "acme")["id"] == "y"
    assert next_job(q, "beta")["id"] == "y"


def test_tenant_rule_then_shorter_runtime():
    q = [_job("k1", "acme", 5, "2024-06-01T09:00:00", 30),
         _job("k2", "beta", 5, "2024-06-01T09:01:00", 400),
         _job("k3", "gamma", 5, "2024-06-01T09:02:00", 90)]
    assert next_job(q, "acme")["id"] == "k3"


def test_equal_runtime_breaks_by_submission():
    q = [_job("m1", "t1", 5, "2024-06-01T09:04:00", 120),
         _job("m2", "t2", 5, "2024-06-01T09:02:00", 120)]
    assert next_job(q, "other")["id"] == "m2"
