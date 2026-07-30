from workerctl import drain_order


def _ids(jobs):
    return [j["id"] for j in jobs]


def _running(id, remaining):
    return {"id": id, "state": "running", "remaining": remaining}


def _queued(id, deadline, idempotent=False):
    return {"id": id, "state": "queued", "deadline": deadline, "idempotent": idempotent}


def test_running_shortest_remaining_first():
    jobs = [_running("a", 90), _running("b", 10), _running("c", 40)]
    run_now, _, _ = drain_order(jobs, 100, 60)
    assert _ids(run_now) == ["b", "c", "a"]


def test_running_ties_break_by_id():
    jobs = [_running("z", 20), _running("a", 20)]
    assert _ids(drain_order(jobs, 0, 60)[0]) == ["a", "z"]


def test_idempotent_in_window_runs_after_in_flight():
    jobs = [_queued("q9", 130, idempotent=True), _running("r", 50)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert _ids(run_now) == ["r", "q9"]
    assert requeue == [] and dropped == []


def test_promoted_jobs_ordered_by_deadline_then_id():
    jobs = [_queued("x", 150, idempotent=True), _queued("y", 120, idempotent=True),
            _queued("w", 120, idempotent=True)]
    run_now, _, _ = drain_order(jobs, 100, 60)
    assert _ids(run_now) == ["w", "y", "x"]


def test_idempotent_outside_window_requeues_in_order():
    jobs = [_queued("far", 300, idempotent=True), _queued("n", 200)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert run_now == []
    assert _ids(requeue) == ["far", "n"]
    assert dropped == []


def test_non_idempotent_never_runs_during_drain():
    jobs = [_queued("plain", 130, idempotent=False)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert run_now == []
    assert _ids(requeue) == ["plain"]


def test_requeue_keeps_original_queue_order():
    jobs = [_queued("z", 300), _queued("a", 180), _queued("m", 240)]
    _, requeue, _ = drain_order(jobs, 100, 60)
    assert _ids(requeue) == ["z", "a", "m"]


def test_exceeded_deadlines_are_dropped():
    jobs = [_queued("old", 40), _queued("ok", 500)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert run_now == []
    assert _ids(requeue) == ["ok"]
    assert _ids(dropped) == ["old"]


def test_expired_idempotent_is_dropped_not_run():
    jobs = [_queued("ghost", 70, idempotent=True)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert run_now == [] and requeue == []
    assert _ids(dropped) == ["ghost"]


def test_dropped_keep_original_order():
    jobs = [_queued("t2", 10), _queued("t1", 20), _queued("live", 400)]
    _, requeue, dropped = drain_order(jobs, 100, 60)
    assert _ids(dropped) == ["t2", "t1"]
    assert _ids(requeue) == ["live"]


def test_window_boundaries_are_inclusive():
    jobs = [_queued("edge", 160, idempotent=True), _queued("at_now", 100, idempotent=True)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert _ids(run_now) == ["at_now", "edge"]
    assert requeue == [] and dropped == []


def test_one_past_the_window_requeues():
    jobs = [_queued("just_out", 161, idempotent=True)]
    run_now, requeue, _ = drain_order(jobs, 100, 60)
    assert run_now == []
    assert _ids(requeue) == ["just_out"]


def test_full_drain_mix():
    jobs = [_running("infl_b", 45), _queued("stale", 20),
            _queued("exp_soon", 155, idempotent=True), _running("infl_a", 5),
            _queued("later", 500), _queued("keep_order", 480),
            _queued("far_idem", 900, idempotent=True)]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert _ids(run_now) == ["infl_a", "infl_b", "exp_soon"]
    assert _ids(requeue) == ["later", "keep_order", "far_idem"]
    assert _ids(dropped) == ["stale"]
