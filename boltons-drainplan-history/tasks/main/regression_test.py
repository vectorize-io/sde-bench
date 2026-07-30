from workerctl import drain_order


def test_drain_plan_at_deploy_signal():
    jobs = [{"id": "r1", "state": "running", "remaining": 5},
            {"id": "r2", "state": "running", "remaining": 30},
            {"id": "q1", "state": "queued", "idempotent": True, "deadline": 140},
            {"id": "q2", "state": "queued", "idempotent": False, "deadline": 900}]
    run_now, requeue, dropped = drain_order(jobs, 100, 60)
    assert [j["id"] for j in run_now] == ["r1", "r2", "q1"]
    assert [j["id"] for j in requeue] == ["q2"]
    assert dropped == []
