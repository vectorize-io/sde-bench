from crmsync import merge_records


def test_sync_duplicate_collapsed():
    primary = [{"email": "Ann@corp.com", "updated": "2024-05-01T09:00:00", "name": "Ann"}]
    incoming = [{"email": "ann@corp.com", "updated": "2024-05-01T15:30:00",
                 "name": "Ann Lee", "phone": "555-0100", "company": "Corp"}]
    out = merge_records(primary, incoming)
    assert len(out) == 1
    assert out[0]["phone"] == "555-0100"
