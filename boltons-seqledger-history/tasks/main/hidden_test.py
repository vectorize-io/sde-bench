import pytest
from auditlog import append_event, SequenceGapError, SequenceConflictError


def _ev(tenant, seq, type="action", payload_hash="h"):
    return {"tenant": tenant, "seq": seq, "type": type, "payload_hash": payload_hash}


def test_gap_rejected_and_nothing_recorded():
    ledger = {}
    append_event(ledger, _ev("t1", 1))
    with pytest.raises(SequenceGapError):
        append_event(ledger, _ev("t1", 5))
    assert [e["seq"] for e in ledger["t1"]] == [1]


def test_first_event_must_be_seq_1():
    with pytest.raises(SequenceGapError):
        append_event({}, _ev("t1", 3))


def test_compaction_advances_by_exactly_100():
    ledger = {}
    append_event(ledger, _ev("t1", 1))
    append_event(ledger, _ev("t1", 2))
    assert append_event(ledger, _ev("t1", 102, type="compaction", payload_hash="c")) is True
    assert [e["seq"] for e in ledger["t1"]] == [1, 2, 102]


def test_compaction_with_any_other_jump_rejected():
    ledger = {}
    append_event(ledger, _ev("t1", 1))
    with pytest.raises(SequenceGapError):
        append_event(ledger, _ev("t1", 51, type="compaction"))
    with pytest.raises(SequenceGapError):
        append_event(ledger, _ev("t1", 2, type="compaction"))


def test_ordinary_event_cannot_jump_like_a_compaction():
    ledger = {}
    append_event(ledger, _ev("t1", 1))
    with pytest.raises(SequenceGapError):
        append_event(ledger, _ev("t1", 101, type="action"))


def test_sequence_continues_after_compaction():
    ledger = {}
    append_event(ledger, _ev("t1", 1))
    append_event(ledger, _ev("t1", 101, type="compaction", payload_hash="c"))
    assert append_event(ledger, _ev("t1", 102)) is True


def test_duplicate_with_matching_hash_is_a_noop():
    ledger = {}
    append_event(ledger, _ev("t1", 1, payload_hash="same"))
    assert append_event(ledger, _ev("t1", 1, payload_hash="same")) is False
    assert len(ledger["t1"]) == 1


def test_duplicate_with_mismatched_hash_raises_conflict():
    ledger = {}
    append_event(ledger, _ev("t1", 1, payload_hash="original"))
    with pytest.raises(SequenceConflictError):
        append_event(ledger, _ev("t1", 1, payload_hash="different"))
    assert ledger["t1"][0]["payload_hash"] == "original"


def test_conflict_check_uses_the_stored_event_mid_sequence():
    ledger = {}
    for i in (1, 2, 3):
        append_event(ledger, _ev("t1", i, payload_hash="h%d" % i))
    assert append_event(ledger, _ev("t1", 2, payload_hash="h2")) is False
    with pytest.raises(SequenceConflictError):
        append_event(ledger, _ev("t1", 2, payload_hash="hX"))
    assert [e["payload_hash"] for e in ledger["t1"]] == ["h1", "h2", "h3"]


def test_tenants_do_not_share_sequences():
    ledger = {}
    append_event(ledger, _ev("a", 1))
    append_event(ledger, _ev("b", 1))
    append_event(ledger, _ev("a", 2))
    with pytest.raises(SequenceGapError):
        append_event(ledger, _ev("b", 3))
