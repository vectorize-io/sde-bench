"""HARD-tier trap batch E for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). Categories (gen/categories.py):
  tagmerge  -> collection-merge  (precedence union + first-casing dedupe + scoped tombstones)
  seqledger -> invariant         (consecutive seq + compaction stride 100 + hash-checked replays)

Hard-tier design goals as in batches A-D: multi-part policies (3+ interacting constraints),
bug reports in symptom vocabulary far from the decision wording, WIDE hidden tests (each policy
component pinned by its own small test function), and two naive guesses per trap, each passing
the repro but failing hidden.

Batch-E extra lever ("buried decision"): each trap's conversation is a LONG (16-turn) meandering
debugging/design session. The policy parts surface piecewise, separated by legitimate unrelated
discussion (logging budgets, rollout staging, CI flakiness of the same module), and at least one
plausible alternative is explicitly REJECTED mid-chat (the rejected alternative is one of the
naive fixes). The full rule is still unambiguously inferable from the chat alone.
"""


# --------------------------------------------------------------------------- tagmerge
# Policy (all parts required): `sources` is an ordered list of tag lists, HIGHEST precedence
# first. Result = union across sources in precedence order, de-duplicated CASE-INSENSITIVELY,
# keeping the casing of the first (highest-precedence) occurrence; output order = first
# occurrence. A tombstone entry "-name" in a source suppresses that tag (matched
# case-insensitively) from all LOWER-precedence sources, but never removes a tag a
# HIGHER-precedence source asserted itself. Tombstones never appear in the output, and an
# unmatched tombstone is silently fine.
# HEAD bug: naive concatenation + exact-string dedupe; "-name" entries pass through as
# literal tags. Naive (a): case-insensitive union but tombstones applied GLOBALLY (a kill
# list that also deletes higher-precedence asserts). Naive (b): case-insensitive union,
# tombstones dropped from the output but never applied at all.

_TAG_HEADER = '"""Tag list merging for the label sync worker."""\n\n\n'

TAGMERGE = {
    "name": "tagmerge",
    "marker": "tombstone",   # the answer-token used by the source-isolation check
    "category": "collection-merge",
    "pkg": "labelsync",
    "module": "labelsync/tags.py",
    "init": '"""labelsync package."""\nfrom .tags import merge_tags\n\n__all__ = ["merge_tags"]\n',
    "import_line": "from labelsync import merge_tags",
    # HEAD bug: concat + exact-string dedupe; dash entries leak into the output as tags
    "bug": (_TAG_HEADER +
            'def merge_tags(sources):\n'
            '    """Merge tag lists from every source into one combined list."""\n'
            '    out = []\n'
            '    for tags in sources:\n'
            '        for tag in tags:\n'
            '            if tag not in out:\n'
            '                out.append(tag)\n'
            '    return out\n'),
    "correct": (_TAG_HEADER +
                'def merge_tags(sources):\n'
                '    """Merge tag lists into one; sources[0] has the highest precedence.\n'
                '\n'
                '    Policy (source-of-truth migration):\n'
                '      - union in precedence order, de-duplicated case-insensitively,\n'
                '        keeping the casing of the first (highest-precedence) occurrence;\n'
                '        output order = first occurrence.\n'
                '      - a tombstone entry "-name" suppresses that tag (matched\n'
                '        case-insensitively) from all LOWER-precedence sources, but never\n'
                '        removes a tag a higher-precedence source asserted itself.\n'
                '      - tombstones never appear in the output; an unmatched tombstone is\n'
                '        silently fine.\n'
                '    """\n'
                '    out = []\n'
                '    seen = set()\n'
                '    blocked = set()\n'
                '    for tags in sources:\n'
                '        level_stones = []\n'
                '        for tag in tags:\n'
                '            if tag.startswith("-"):\n'
                '                level_stones.append(tag[1:].lower())\n'
                '            else:\n'
                '                low = tag.lower()\n'
                '                if low not in seen and low not in blocked:\n'
                '                    seen.add(low)\n'
                '                    out.append(tag)\n'
                '        blocked.update(level_stones)\n'
                '    return out\n'),
    "naive": [
        # case-insensitive union + dash entries hidden, but applied as a GLOBAL kill list
        # (a lower-precedence "-name" also deletes a higher-precedence assert)
        (_TAG_HEADER +
         'def merge_tags(sources):\n'
         '    """Merge tag lists case-insensitively, honouring "-name" removal entries."""\n'
         '    removed = set()\n'
         '    for tags in sources:\n'
         '        for tag in tags:\n'
         '            if tag.startswith("-"):\n'
         '                removed.add(tag[1:].lower())\n'
         '    out = []\n'
         '    seen = set()\n'
         '    for tags in sources:\n'
         '        for tag in tags:\n'
         '            if tag.startswith("-"):\n'
         '                continue\n'
         '            low = tag.lower()\n'
         '            if low not in seen and low not in removed:\n'
         '                seen.add(low)\n'
         '                out.append(tag)\n'
         '    return out\n'),
        # case-insensitive union, dash entries dropped from the output but never applied
        (_TAG_HEADER +
         'def merge_tags(sources):\n'
         '    """Merge tag lists case-insensitively, skipping "-name" bookkeeping entries."""\n'
         '    out = []\n'
         '    seen = set()\n'
         '    for tags in sources:\n'
         '        for tag in tags:\n'
         '            if tag.startswith("-"):\n'
         '                continue\n'
         '            low = tag.lower()\n'
         '            if low not in seen:\n'
         '                seen.add(low)\n'
         '                out.append(tag)\n'
         '    return out\n'),
    ],
    "decision_subject": "fix: precedence-aware tag merging with scoped tombstone suppression",
    "decision_rationale": (
        "The source-of-truth migration made merge_tags' input an ordered list of sources, highest "
        "precedence first (CMDB, then cloud provider, then legacy inventory), and the old "
        "concat-and-exact-dedupe produced every symptom ops reported. merge_tags now unions sources "
        "in precedence order, de-duplicated case-insensitively, keeping the casing of the first "
        "(highest-precedence) occurrence, in first-occurrence order. A tombstone entry '-name' "
        "suppresses that tag (matched case-insensitively) from all LOWER-precedence sources, but "
        "never removes a tag a higher-precedence source asserted itself - a tombstone speaks only "
        "for the sources below it, NOT a global kill list, or the junkiest source could delete the "
        "source of truth's tags. Tombstones never appear in the output, and an unmatched tombstone "
        "is silently fine - ops writes them speculatively."),
    "conversation": [
        {"role": "user", "text": "Since the source-of-truth migration went live the tag situation on resources is a mess: the UI shows tags ops explicitly removed weeks ago, some tags appear twice with different capitalization, and there are literal dash-prefixed junk tags like '-decommissioned' rendered as if they were real tags."},
        {"role": "assistant", "text": "merge_tags just concatenates every source's list and drops exact-string duplicates, so 'Env:Prod' and 'env:prod' both survive and anything unusual passes straight through. Easiest cleanup: lowercase every tag on the way in and de-duplicate on the lowercased value - output would be all-lowercase and the duplicates collapse."},
        {"role": "user", "text": "De-duplicating case-insensitively is right, but do not lowercase the output - the Terraform provider treats tag casing as significant downstream and half our saved searches match exact casing. Keep one occurrence with its original casing. And remember what the migration actually changed: merge_tags now gets an ordered list of sources, index 0 is the highest precedence - the CMDB - then the cloud provider, then the legacy inventory."},
        {"role": "assistant", "text": "Understood, no lowercasing of the output. Unrelated while I'm in this file - the merge worker currently logs nothing when it drops a duplicate. Do you want a log line per dropped tag so support can answer the 'where did my tag go' tickets?"},
        {"role": "user", "text": "Debug level only, one line per merge run with counts, not per tag - the worker handles 40k resources a run and we already blew the log quota once this quarter. Also a heads-up if you run the suite: test_tags has been flaky on CI lately, the order-dependence one - rerun before you blame your change."},
        {"role": "assistant", "text": "Noted on both. Back to the merge: when the same tag appears in several sources with different casing, which casing survives - and what order should the merged list come out in?"},
        {"role": "user", "text": "The casing from the highest-precedence source that asserts the tag: if the CMDB says 'Env:Prod' and the provider says 'env:prod', the output says 'Env:Prod'. Order is first occurrence, walking the sources in precedence order and keeping each source's own order - the reconciler diffs the output, so it has to be deterministic."},
        {"role": "assistant", "text": "That leaves the dash entries. They look like corruption from the importer - should I just filter out anything starting with '-' and file a ticket against the importer?"},
        {"role": "user", "text": "They're not corruption, they're deliberate: the ops sync writes '-name' as a tombstone meaning 'remove this tag' - that's how ops deletes tags now. So they must never show up in the output as literal tags, but they carry meaning you have to apply, not just strip."},
        {"role": "assistant", "text": "Then I'll build a kill list: collect every '-name' across all sources and strip that tag from the entire merged result, wherever it came from."},
        {"role": "user", "text": "No - that's exactly the wrong scope, and it's why we didn't do this in the collector. A tombstone speaks only for the sources BELOW it: '-standby' from the CMDB suppresses 'standby' coming from the provider or the legacy inventory, but a '-critical' from the legacy inventory must never delete a 'critical' the CMDB itself asserts. If a higher-precedence source asserted the tag, it stays. A global kill list lets the junkiest source delete the source of truth's tags."},
        {"role": "assistant", "text": "Got it - tombstones scope downward only, never upward. What about a tombstone that matches nothing below it: hard error, warning, or ignore?"},
        {"role": "user", "text": "Silently fine. Ops writes tombstones speculatively for tags that may not exist everywhere yet - erroring would wedge the whole sync. And tombstone matching is case-insensitive, same as the dedupe: '-Legacy' kills 'legacy'."},
        {"role": "assistant", "text": "One more thing before I write this up - rollout. Do you want the new merge behind a feature flag, or shipped straight to the merge worker?"},
        {"role": "user", "text": "No flag - flags rot in that worker. Stage it to the internal org's sync first, watch one full cycle, then everywhere, same as we did for the pagination fix."},
        {"role": "assistant", "text": "Final shape of merge_tags then: sources arrive highest precedence first; union in precedence order, de-duplicated case-insensitively, keeping the casing of the first - highest-precedence - occurrence, output in first-occurrence order. A '-name' tombstone suppresses that tag, matched case-insensitively, from all lower-precedence sources only - it never removes a tag a higher-precedence source asserted. Tombstones never appear in the output, and an unmatched tombstone is silently ignored."},
    ],
    "existing_test": (
        'from labelsync import merge_tags\n\n\n'
        'def test_single_source_passthrough():\n'
        '    assert merge_tags([["env:prod", "team-core"]]) == ["env:prod", "team-core"]\n\n\n'
        'def test_disjoint_sources_concatenate_in_order():\n'
        '    assert merge_tags([["a"], ["b", "c"]]) == ["a", "b", "c"]\n\n\n'
        'def test_exact_duplicate_collapses():\n'
        '    assert merge_tags([["infra"], ["infra"]]) == ["infra"]\n\n\n'
        'def test_empty_inputs():\n'
        '    assert merge_tags([]) == []\n'
        '    assert merge_tags([[], []]) == []\n'),
    # case-only duplicate + a dash entry matching nothing below it: every candidate policy
    # produces the same clean list; only the HEAD bug keeps both casings and leaks the dash.
    "repro_test": (
        'from labelsync import merge_tags\n\n\n'
        'def test_migrated_sources_merge_cleanly():\n'
        '    sources = [["Env:Prod", "team-core"],\n'
        '               ["env:prod", "-decommissioned", "region-eu"]]\n'
        '    assert merge_tags(sources) == ["Env:Prod", "team-core", "region-eu"]\n'),
    "hidden_test": (
        'from labelsync import merge_tags\n\n\n'
        'def test_dedupe_keeps_highest_precedence_casing():\n'
        '    assert merge_tags([["Prod", "Web"], ["prod", "PROD", "db"]]) == ["Prod", "Web", "db"]\n\n\n'
        'def test_tombstone_suppresses_lower_precedence_sources():\n'
        '    assert merge_tags([["-legacy"], ["legacy", "web"]]) == ["web"]\n\n\n'
        'def test_tombstone_cannot_remove_higher_precedence_assert():\n'
        '    assert merge_tags([["critical"], ["-critical", "db"]]) == ["critical", "db"]\n\n\n'
        'def test_tombstone_matches_case_insensitively():\n'
        '    assert merge_tags([["-Legacy"], ["legacy", "APP"]]) == ["APP"]\n\n\n'
        'def test_mid_level_tombstone_only_affects_lower_sources():\n'
        '    assert merge_tags([["alpha"], ["-beta"], ["beta", "gamma"]]) == ["alpha", "gamma"]\n\n\n'
        'def test_tombstoned_tag_stays_out_even_when_reasserted_below():\n'
        '    assert merge_tags([["ops", "-standby"], ["standby", "ops"]]) == ["ops"]\n\n\n'
        'def test_unmatched_tombstones_are_silently_fine():\n'
        '    assert merge_tags([["-ghost"], ["app"]]) == ["app"]\n'
        '    assert merge_tags([["-a", "-b"]]) == []\n\n\n'
        'def test_first_occurrence_order_is_kept():\n'
        '    assert merge_tags([["b", "a"], ["c", "A"]]) == ["b", "a", "c"]\n\n\n'
        'def test_case_variants_across_three_sources_collapse_to_topmost():\n'
        '    assert merge_tags([["Tier:Gold"], ["tier:gold"], ["TIER:GOLD", "extra"]]) == ["Tier:Gold", "extra"]\n'),
    "bug_report": ("After the source-of-truth migration, resources show tags ops explicitly removed, "
                   "and some tags appear twice with different capitalization; there are also literal "
                   "dash-prefixed junk tags in the UI. A failing repro is at tests/test_regression.py. "
                   "Fix merge_tags so the merged list reflects what the sources actually assert, "
                   "without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- seqledger
# Policy (all parts required): per-tenant seq must be exactly last_seq + 1 (an empty trail
# counts as last seq 0, so a tenant's first event is seq 1); any gap raises SequenceGapError.
# EXCEPT a compaction marker event (type == "compaction"), which must advance seq by EXACTLY
# 100 (the archiver's documented batch size) - any other jump, including +1, is rejected the
# same way. A duplicate seq is an idempotent no-op (returns False) ONLY when the event's
# payload_hash matches the stored one; a mismatched hash raises SequenceConflictError -
# never silently overwrite, never silently ignore.
# HEAD bug: accepts any seq greater than the last (gaps allowed) and duplicates always
# overwrite in place. Naive (a): strictly consecutive but compaction not special-cased
# (rejects the +100 jump) and duplicates always no-op regardless of hash. Naive (b):
# consecutive + compaction +100, but duplicates always no-op, hash ignored.

_LEDGER_HEADER = (
    '"""Append-only per-tenant audit ledger."""\n\n\n'
    'class SequenceGapError(Exception):\n'
    '    """Raised when an event\'s seq does not follow the tenant\'s sequence."""\n\n\n'
    'class SequenceConflictError(Exception):\n'
    '    """Raised when an event conflicts with one already recorded."""\n\n\n')


def _ledger_mod(dup_lines, doc=""):
    return (_LEDGER_HEADER +
            'def append_event(ledger, event):\n'
            f'    """Record an audit event in the tenant\'s append-only sequence.{doc}"""\n'
            '    events = ledger.setdefault(event["tenant"], [])\n'
            '    seq = event["seq"]\n'
            '    last = events[-1]["seq"] if events else 0\n'
            '    if seq <= last:\n'
            + dup_lines +
            '    step = seq - last\n'
            '    if event.get("type") == "compaction":\n'
            '        if step != 100:\n'
            '            raise SequenceGapError("compaction for %s must advance seq by exactly 100, got +%d"\n'
            '                                   % (event["tenant"], step))\n'
            '    elif step != 1:\n'
            '        raise SequenceGapError("gap for %s: expected seq %d, got %d"\n'
            '                               % (event["tenant"], last + 1, seq))\n'
            '    events.append(dict(event))\n'
            '    return True\n')


SEQLEDGER = {
    "name": "seqledger",
    "marker": "batch size",   # the answer-token used by the source-isolation check
    "category": "invariant",
    "pkg": "auditlog",
    "module": "auditlog/ledger.py",
    "init": ('"""auditlog package."""\n'
             'from .ledger import append_event, SequenceGapError, SequenceConflictError\n\n'
             '__all__ = ["append_event", "SequenceGapError", "SequenceConflictError"]\n'),
    "import_line": "from auditlog import append_event, SequenceGapError, SequenceConflictError",
    # HEAD bug: any increasing seq accepted (gaps become silent holes); a replayed seq
    # overwrites the stored event in place.
    "bug": (_LEDGER_HEADER +
            'def append_event(ledger, event):\n'
            '    """Record an audit event in the tenant\'s sequence."""\n'
            '    events = ledger.setdefault(event["tenant"], [])\n'
            '    seq = event["seq"]\n'
            '    for i, stored in enumerate(events):\n'
            '        if stored["seq"] == seq:\n'
            '            events[i] = dict(event)\n'
            '            return True\n'
            '    if events and seq < events[-1]["seq"]:\n'
            '        raise SequenceGapError("stale seq %d for %s" % (seq, event["tenant"]))\n'
            '    events.append(dict(event))\n'
            '    return True\n'),
    "correct": _ledger_mod(
        ('        for stored in events:\n'
         '            if stored["seq"] == seq:\n'
         '                if stored["payload_hash"] == event["payload_hash"]:\n'
         '                    return False\n'
         '                raise SequenceConflictError("seq %d for %s: payload_hash mismatch"\n'
         '                                            % (seq, event["tenant"]))\n'
         '        raise SequenceGapError("seq %d for %s is inside an archived range"\n'
         '                               % (seq, event["tenant"]))\n'),
        doc=("\n\n    Sequence policy (compliance-pinned):\n"
             "      - seq must be exactly last_seq + 1 (an empty trail counts as last seq 0,\n"
             "        so a tenant's first event is seq 1); any gap raises SequenceGapError\n"
             "        at write time.\n"
             "      - a compaction marker (type == \"compaction\") must advance seq by\n"
             "        EXACTLY 100, the archiver's documented batch size; any other jump,\n"
             "        including +1, raises SequenceGapError.\n"
             "      - a duplicate seq is an idempotent no-op (returns False) ONLY when its\n"
             "        payload_hash matches the stored event; a mismatch raises\n"
             "        SequenceConflictError. Never overwrite, never silently ignore.\n    ")),
    "naive": [
        # strictly consecutive, but no compaction carve-out (the +100 marker is rejected)
        # and any duplicate is an unconditional no-op, hash ignored
        (_LEDGER_HEADER +
         'def append_event(ledger, event):\n'
         '    """Record an audit event; seq must be strictly consecutive per tenant."""\n'
         '    events = ledger.setdefault(event["tenant"], [])\n'
         '    seq = event["seq"]\n'
         '    last = events[-1]["seq"] if events else 0\n'
         '    if seq <= last:\n'
         '        return False\n'
         '    if seq != last + 1:\n'
         '        raise SequenceGapError("gap for %s: expected seq %d, got %d"\n'
         '                               % (event["tenant"], last + 1, seq))\n'
         '    events.append(dict(event))\n'
         '    return True\n'),
        # consecutive + compaction stride, but duplicates are an unconditional no-op
        _ledger_mod('        return False\n'),
    ],
    "decision_subject": "fix: enforce the audit ledger sequence contract "
                        "(consecutive seq, compaction stride, hash-checked replays)",
    "decision_rationale": (
        "The compliance findings traced to append_event accepting any increasing seq (lost messages "
        "became silent holes) and overwriting replayed events in place (how primary and replica "
        "diverged). Per-tenant seq must be exactly last_seq + 1 - an empty trail counts as last seq "
        "0, so a tenant's first event is seq 1 - and any gap raises SequenceGapError at write time. "
        "The single exception is the archiver's compaction marker (type == 'compaction'), which must "
        "advance seq by EXACTLY 100, the archiver's documented batch size; any other jump, including "
        "+1, is rejected the same way - no tolerance knob, that turns into 'gaps allowed' within a "
        "quarter. A duplicate seq is an idempotent no-op (returns False) only when its payload_hash "
        "matches the stored event; a mismatch raises SequenceConflictError - the ledger never "
        "overwrites and never silently ignores a conflicting replay, because swallowing mismatches "
        "is how the divergence went undetected for a month."),
    "conversation": [
        {"role": "user", "text": "Compliance ran the quarterly export against the audit ledger and flagged us: month-end reconciliation shows entries missing from some tenants' trails, and for one incident the record in the primary export doesn't match what the replica export shows. Legal is involved now, so this needs to be right, not fast."},
        {"role": "assistant", "text": "Looking at append_event: it accepts any seq greater than the tenant's last one - a lost message just becomes a silent hole - and when a seq arrives twice it overwrites the stored event in place, which is how primary and replica can end up disagreeing depending on delivery order. I'd make seq strictly consecutive and turn any duplicate into an idempotent no-op."},
        {"role": "user", "text": "Strictly consecutive, yes: each tenant's seq must be exactly last + 1, and a gap has to be rejected loudly at write time - raise SequenceGapError, don't log-and-accept. But park the duplicate half of your plan for a moment, there's more to it than a blanket no-op."},
        {"role": "assistant", "text": "Parked. Before that - the tenants that already have holes from the old behaviour: should append_event try to repair or backfill those when it notices them?"},
        {"role": "user", "text": "No, append_event stays a pure guard - repair is a one-off backfill job the data team is writing against the archived stream, don't couple them. While you're in there though: whatever you do has to keep working with the archiver. That's the thing nobody remembers until it breaks."},
        {"role": "assistant", "text": "That's actually my worry with strict last + 1: the archiver's compaction markers jump the sequence forward when a batch is archived. Should I add a config knob - a maximum allowed gap, tolerance configurable per tenant?"},
        {"role": "user", "text": "No knob - a tolerance setting turns back into 'gaps allowed' within a quarter, someone will crank it. The rule is fixed: an event with type 'compaction' must advance the seq by exactly 100, because 100 is the archiver's documented batch size and it never emits partial batches. Exactly 100 - a compaction that jumps 50, or one that only advances by 1, is just as invalid as a gap and gets the same SequenceGapError. Ordinary events never get to jump, period."},
        {"role": "assistant", "text": "Understood: +1 for everything, except type == 'compaction' which must be +100 exactly. Different topic - when we reject a write, what should the log line carry? The full event payload for debugging?"},
        {"role": "user", "text": "Tenant, seq, and the reason only - payloads can carry PII and the audit pipeline feeds the SIEM, we are not spraying payloads into it. Oh, and fair warning: test_ledger has been flaky on CI this week - the wall-clock timestamp assertion - if that one goes red it's not you."},
        {"role": "assistant", "text": "Noted. Now the parked duplicate question. My default would be: any event whose seq we've already stored is a replay - return early as an idempotent no-op and never touch the stored record."},
        {"role": "user", "text": "That blanket no-op is exactly what we can't do - it's the other half of the compliance finding. If the incoming duplicate's payload_hash matches the stored event, fine, that's a redelivery: no-op, don't append, don't rewrite. But if the hash differs, something is trying to record a different version of history under an already-used seq, and that must raise SequenceConflictError. Never overwrite the stored event, and never silently swallow the mismatch either - swallowing is how the primary/replica divergence went undetected for a month."},
        {"role": "assistant", "text": "Makes sense. So the return contract is: True when the event was appended, False for the matching-hash redelivery no-op, and exceptions for gaps and conflicts?"},
        {"role": "user", "text": "Exactly. And to close the loop on 'consecutive': a brand-new tenant starts at seq 1 - treat an empty trail as last seq 0, so a first event arriving with seq 3 is a gap like any other."},
        {"role": "assistant", "text": "Got it. On rollout - this will start rejecting writes that used to succeed. Straight to every region, or staged?"},
        {"role": "user", "text": "Canary region first, with the gap and conflict rejections graphed - if a producer is genuinely broken I want to see it as a rejection spike in canary, not as a compliance finding next quarter. Everywhere else after two clean days."},
        {"role": "assistant", "text": "Recap of append_event's contract: per-tenant seq strictly consecutive - exactly last + 1, an empty trail counts as 0 so the first event is seq 1 - and anything else raises SequenceGapError; the single exception is a type == 'compaction' event, which must advance seq by exactly 100, the archiver's batch size, any other jump rejected the same way; a duplicate seq is an idempotent no-op returning False only when its payload_hash matches the stored event, and a mismatched hash raises SequenceConflictError - the ledger never overwrites and never silently ignores a conflicting replay."},
    ],
    "existing_test": (
        'from auditlog import append_event\n\n\n'
        'def test_consecutive_appends():\n'
        '    ledger = {}\n'
        '    for i, h in enumerate(["h1", "h2", "h3"], start=1):\n'
        '        assert append_event(ledger, {"tenant": "acme", "seq": i,\n'
        '                                     "type": "action", "payload_hash": h}) is True\n'
        '    assert [e["seq"] for e in ledger["acme"]] == [1, 2, 3]\n\n\n'
        'def test_tenants_have_independent_sequences():\n'
        '    ledger = {}\n'
        '    append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "a"})\n'
        '    append_event(ledger, {"tenant": "globex", "seq": 1, "type": "action", "payload_hash": "g"})\n'
        '    assert len(ledger["acme"]) == 1\n'
        '    assert len(ledger["globex"]) == 1\n\n\n'
        'def test_event_data_is_recorded():\n'
        '    ledger = {}\n'
        '    append_event(ledger, {"tenant": "t", "seq": 1, "type": "login", "payload_hash": "abc"})\n'
        '    assert ledger["t"][0]["type"] == "login"\n'
        '    assert ledger["t"][0]["payload_hash"] == "abc"\n'),
    # a plain gap must be rejected (every candidate agrees) and a replay must never rewrite
    # the stored record, however the function reacts to it; only the HEAD bug fails both.
    "repro_test": (
        'import pytest\nfrom auditlog import append_event, SequenceGapError\n\n\n'
        'def test_missing_entry_rejected_at_write_time():\n'
        '    ledger = {}\n'
        '    append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "a1"})\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event(ledger, {"tenant": "acme", "seq": 3, "type": "action", "payload_hash": "a3"})\n\n\n'
        'def test_replayed_event_never_rewrites_the_record():\n'
        '    ledger = {}\n'
        '    append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "original"})\n'
        '    try:\n'
        '        append_event(ledger, {"tenant": "acme", "seq": 1, "type": "action", "payload_hash": "tampered"})\n'
        '    except Exception:\n'
        '        pass\n'
        '    assert ledger["acme"][0]["payload_hash"] == "original"\n'),
    "hidden_test": (
        'import pytest\nfrom auditlog import append_event, SequenceGapError, SequenceConflictError\n\n\n'
        'def _ev(tenant, seq, type="action", payload_hash="h"):\n'
        '    return {"tenant": tenant, "seq": seq, "type": type, "payload_hash": payload_hash}\n\n\n'
        'def test_gap_rejected_and_nothing_recorded():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1))\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event(ledger, _ev("t1", 5))\n'
        '    assert [e["seq"] for e in ledger["t1"]] == [1]\n\n\n'
        'def test_first_event_must_be_seq_1():\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event({}, _ev("t1", 3))\n\n\n'
        'def test_compaction_advances_by_exactly_100():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1))\n'
        '    append_event(ledger, _ev("t1", 2))\n'
        '    assert append_event(ledger, _ev("t1", 102, type="compaction", payload_hash="c")) is True\n'
        '    assert [e["seq"] for e in ledger["t1"]] == [1, 2, 102]\n\n\n'
        'def test_compaction_with_any_other_jump_rejected():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1))\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event(ledger, _ev("t1", 51, type="compaction"))\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event(ledger, _ev("t1", 2, type="compaction"))\n\n\n'
        'def test_ordinary_event_cannot_jump_like_a_compaction():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1))\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event(ledger, _ev("t1", 101, type="action"))\n\n\n'
        'def test_sequence_continues_after_compaction():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1))\n'
        '    append_event(ledger, _ev("t1", 101, type="compaction", payload_hash="c"))\n'
        '    assert append_event(ledger, _ev("t1", 102)) is True\n\n\n'
        'def test_duplicate_with_matching_hash_is_a_noop():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1, payload_hash="same"))\n'
        '    assert append_event(ledger, _ev("t1", 1, payload_hash="same")) is False\n'
        '    assert len(ledger["t1"]) == 1\n\n\n'
        'def test_duplicate_with_mismatched_hash_raises_conflict():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("t1", 1, payload_hash="original"))\n'
        '    with pytest.raises(SequenceConflictError):\n'
        '        append_event(ledger, _ev("t1", 1, payload_hash="different"))\n'
        '    assert ledger["t1"][0]["payload_hash"] == "original"\n\n\n'
        'def test_conflict_check_uses_the_stored_event_mid_sequence():\n'
        '    ledger = {}\n'
        '    for i in (1, 2, 3):\n'
        '        append_event(ledger, _ev("t1", i, payload_hash="h%d" % i))\n'
        '    assert append_event(ledger, _ev("t1", 2, payload_hash="h2")) is False\n'
        '    with pytest.raises(SequenceConflictError):\n'
        '        append_event(ledger, _ev("t1", 2, payload_hash="hX"))\n'
        '    assert [e["payload_hash"] for e in ledger["t1"]] == ["h1", "h2", "h3"]\n\n\n'
        'def test_tenants_do_not_share_sequences():\n'
        '    ledger = {}\n'
        '    append_event(ledger, _ev("a", 1))\n'
        '    append_event(ledger, _ev("b", 1))\n'
        '    append_event(ledger, _ev("a", 2))\n'
        '    with pytest.raises(SequenceGapError):\n'
        '        append_event(ledger, _ev("b", 3))\n'),
    "bug_report": ("Compliance export flagged our audit trail: month-end reconciliation shows missing "
                   "entries, and one incident's record differs between the primary and the replica "
                   "export. A failing repro is at tests/test_regression.py. Fix append_event so the "
                   "audit trail stays complete and consistent, without breaking existing behaviour."),
}


TRAPS_HARD_E = {t["name"]: t for t in [TAGMERGE, SEQLEDGER]}
