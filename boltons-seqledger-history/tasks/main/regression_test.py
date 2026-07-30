import pytest
from auditlog import append_event, SequenceGapError


def test_missing_entry_rejected_at_write_time():
    ledger = {}
    append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "a1"})
    with pytest.raises(SequenceGapError):
        append_event(ledger, {"tenant": "acme", "seq": 3, "type": "action", "payload_hash": "a3"})


def test_replayed_event_never_rewrites_the_record():
    ledger = {}
    append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "original"})
    try:
        append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "tampered"})
    except Exception:
        pass
    assert ledger["acme"][0]["payload_hash"] == "original"
