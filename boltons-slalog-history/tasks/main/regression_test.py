from slalog import downtime_minutes


def test_concurrent_alerts_not_double_counted():
    incidents = [{"start": "2024-06-10T10:00:00", "end": "2024-06-10T10:30:00"},
                 {"start": "2024-06-10T10:15:00", "end": "2024-06-10T10:45:00"}]
    assert downtime_minutes(incidents, []) == 45.0
