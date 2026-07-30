from slalog import downtime_minutes


def test_overlapping_windows_merge():
    inc = [{"start": "2024-06-01T13:00:00", "end": "2024-06-01T13:40:00"},
           {"start": "2024-06-01T13:20:00", "end": "2024-06-01T14:00:00"}]
    assert downtime_minutes(inc, []) == 60.0


def test_touching_windows_merge_into_one_outage():
    inc = [{"start": "2024-06-02T09:00:00", "end": "2024-06-02T09:00:40"},
           {"start": "2024-06-02T09:00:40", "end": "2024-06-02T09:02:00"}]
    assert downtime_minutes(inc, []) == 2.0


def test_sub_minute_blip_ignored():
    inc = [{"start": "2024-06-03T10:00:00", "end": "2024-06-03T10:00:45"}]
    assert downtime_minutes(inc, []) == 0.0


def test_exactly_sixty_seconds_counts():
    inc = [{"start": "2024-06-03T11:00:00", "end": "2024-06-03T11:01:00"}]
    assert downtime_minutes(inc, []) == 1.0


def test_blip_threshold_applies_to_merged_window():
    inc = [{"start": "2024-06-04T10:00:00", "end": "2024-06-04T10:00:50"},
           {"start": "2024-06-04T10:00:35", "end": "2024-06-04T10:01:30"}]
    assert downtime_minutes(inc, []) == 1.5


def test_late_announced_maintenance_still_counts():
    inc = [{"start": "2024-06-05T02:00:00", "end": "2024-06-05T04:00:00"}]
    maint = [{"start": "2024-06-05T02:30:00", "end": "2024-06-05T03:30:00",
              "announced_at": "2024-06-05T00:30:00"}]
    assert downtime_minutes(inc, maint) == 120.0


def test_well_announced_maintenance_excluded():
    inc = [{"start": "2024-06-06T02:00:00", "end": "2024-06-06T04:00:00"}]
    maint = [{"start": "2024-06-06T02:30:00", "end": "2024-06-06T03:30:00",
              "announced_at": "2024-06-03T09:00:00"}]
    assert downtime_minutes(inc, maint) == 60.0


def test_exactly_24h_notice_qualifies():
    inc = [{"start": "2024-06-10T05:00:00", "end": "2024-06-10T06:00:00"}]
    maint = [{"start": "2024-06-10T05:00:00", "end": "2024-06-10T06:00:00",
              "announced_at": "2024-06-09T05:00:00"}]
    assert downtime_minutes(inc, maint) == 0.0


def test_partial_maintenance_overlap():
    inc = [{"start": "2024-06-11T01:00:00", "end": "2024-06-11T02:00:00"}]
    maint = [{"start": "2024-06-11T01:30:00", "end": "2024-06-11T02:30:00",
              "announced_at": "2024-06-08T12:00:00"}]
    assert downtime_minutes(inc, maint) == 30.0


def test_maintenance_outside_incident_ignored():
    inc = [{"start": "2024-06-12T10:00:00", "end": "2024-06-12T10:30:00"}]
    maint = [{"start": "2024-06-12T11:00:00", "end": "2024-06-12T12:00:00",
              "announced_at": "2024-06-09T09:00:00"}]
    assert downtime_minutes(inc, maint) == 30.0


def test_full_month_scenario():
    inc = [{"start": "2024-06-20T08:00:00", "end": "2024-06-20T08:30:00"},
           {"start": "2024-06-20T08:20:00", "end": "2024-06-20T09:00:00"},
           {"start": "2024-06-21T12:00:00", "end": "2024-06-21T12:00:20"}]
    maint = [{"start": "2024-06-20T08:30:00", "end": "2024-06-20T09:00:00",
              "announced_at": "2024-06-20T06:30:00"}]
    assert downtime_minutes(inc, maint) == 60.0
