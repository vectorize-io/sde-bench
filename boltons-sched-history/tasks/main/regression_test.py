from jobsched import next_job


def test_tenant_not_scheduled_twice_in_a_row():
    q = [{"id": "a1", "tenant": "acme", "priority": 5,
          "submitted_at": "2024-06-01T09:00:00", "est_runtime": 120},
         {"id": "b1", "tenant": "beta", "priority": 5,
          "submitted_at": "2024-06-01T09:05:00", "est_runtime": 120}]
    assert next_job(q, "acme")["id"] == "b1"
