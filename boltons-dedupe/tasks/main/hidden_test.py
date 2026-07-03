from crmsync import merge_records


def test_key_is_case_insensitive_same_day():
    primary = [{"email": "Bob@x.com", "updated": "2024-01-02T08:00:00", "name": "Bob", "phone": "1"}]
    incoming = [{"email": "bob@x.com", "updated": "2024-01-02T09:00:00"}]
    out = merge_records(primary, incoming)
    assert len(out) == 1
    assert out[0].get("name") == "Bob"


def test_different_day_is_not_a_duplicate():
    primary = [{"email": "bob@x.com", "updated": "2024-01-02T23:00:00", "name": "Bob"}]
    incoming = [{"email": "bob@x.com", "updated": "2024-01-03T01:00:00", "name": "Bob"}]
    assert len(merge_records(primary, incoming)) == 2


def test_richer_record_survives_even_if_older():
    primary = [{"email": "eve@x.com", "updated": "2024-02-01T08:00:00",
                "name": "Eve", "phone": "22", "company": "X"}]
    incoming = [{"email": "eve@x.com", "updated": "2024-02-01T18:00:00", "name": "Eve"}]
    out = merge_records(primary, incoming)
    assert len(out) == 1
    assert out[0].get("company") == "X"


def test_richer_incoming_wins_even_if_earlier():
    primary = [{"email": "sam@x.com", "updated": "2024-02-05T18:00:00", "name": "Sam"}]
    incoming = [{"email": "sam@x.com", "updated": "2024-02-05T08:00:00",
                 "name": "Sam", "phone": "33"}]
    out = merge_records(primary, incoming)
    assert len(out) == 1
    assert out[0].get("phone") == "33"


def test_empty_string_fields_do_not_count():
    primary = [{"email": "kim@x.com", "updated": "2024-03-01T10:00:00",
                "name": "", "phone": "", "company": ""}]
    incoming = [{"email": "kim@x.com", "updated": "2024-03-01T11:00:00", "name": "Kim"}]
    out = merge_records(primary, incoming)
    assert len(out) == 1
    assert out[0].get("name") == "Kim"


def test_even_match_keeps_the_crm_record():
    primary = [{"email": "joe@x.com", "updated": "2024-04-01T09:00:00", "name": "Joe P"}]
    incoming = [{"email": "joe@x.com", "updated": "2024-04-01T12:00:00", "name": "Joe I"}]
    out = merge_records(primary, incoming)
    assert len(out) == 1
    assert out[0]["name"] == "Joe P"


def test_output_order_primary_then_new():
    primary = [{"email": "p1@x.com", "updated": "2024-05-01T09:00:00", "name": "P1"},
               {"email": "p2@x.com", "updated": "2024-05-01T09:05:00", "name": "P2"}]
    incoming = [{"email": "n1@x.com", "updated": "2024-05-01T10:00:00", "name": "N1"},
                {"email": "p1@x.com", "updated": "2024-05-01T11:00:00"}]
    out = merge_records(primary, incoming)
    assert [r["email"] for r in out] == ["p1@x.com", "p2@x.com", "n1@x.com"]
    assert out[0]["name"] == "P1"
