"""HARD-tier trap library (batch A) for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). These traps are harder on purpose:
multi-part policies, a bug report written in symptom vocabulary far from the decision wording,
and WIDE hidden tests (many assertions across several functions) so a truncated pytest tail
reveals only part of the rule. Each naive guess passes the repro but fails hidden.

Categories (see gen/categories.py taxonomy):
  dedupe    -> collection-merge   (how duplicate records combine: key + winner + tie)
  trimstats -> numeric-policy     (the exact trimming rule before a percentile)
  sched     -> ordering           (the order/eligibility rules for picking the next job)
"""


# --------------------------------------------------------------------------- dedupe
# Policy: duplicate = same email (case-insensitive) on the same calendar DAY of `updated`;
# on a duplicate the record with more non-empty fields wins ("most-filled wins" -- sync jobs
# strip fields, so keep-latest loses data); on a filled-count tie the record from `primary`
# wins (the CRM is the source of truth). Output: primary order first, then new incoming.

def _dedupe_mod(key_expr, win_expr, doc="", helpers=""):
    return (f'"""CRM record de-duplication for sync jobs."""\n{helpers}\n\n'
            f'def merge_records(primary, incoming):\n'
            f'    """Merge incoming sync records into the primary list, dropping duplicate contacts.{doc}"""\n'
            f'    out = []\n'
            f'    slot = {{}}\n'
            f'    for rec in primary + incoming:\n'
            f'        key = {key_expr}\n'
            f'        if key in slot:\n'
            f'            i = slot[key]\n'
            f'            if {win_expr}:\n'
            f'                out[i] = rec\n'
            f'        else:\n'
            f'            slot[key] = len(out)\n'
            f'            out.append(rec)\n'
            f'    return out\n')


_DEDUPE_KEY = '(rec["email"].lower(), rec["updated"][:10])'

DEDUPE = {
    "name": "dedupe",
    "marker": "most-filled",   # the answer-token used by the source-isolation check
    "pkg": "crmsync",
    "module": "crmsync/dedupe.py",
    "init": '"""crmsync package."""\nfrom .dedupe import merge_records\n\n__all__ = ["merge_records"]\n',
    "import_line": "from crmsync import merge_records",
    # HEAD bug: exact (email, updated) equality, later record simply wins
    "bug": _dedupe_mod('(rec["email"], rec["updated"])', 'True'),
    "correct": _dedupe_mod(
        _DEDUPE_KEY,
        '_filled(rec) > _filled(out[i])',
        doc=("\n\n    Duplicate = same email (case-insensitive) with the same DAY in `updated`.\n"
             "    On a duplicate the most-filled record wins (non-empty fields; sync jobs\n"
             "    strip fields, so keep-latest loses data); on a filled-count tie the record\n"
             "    from `primary` wins (the CRM is the source of truth). Output keeps primary\n"
             "    order first, then new incoming records in their order.\n    "),
        helpers=('\n\ndef _filled(rec):\n'
                 '    return sum(1 for v in rec.values() if v not in (None, ""))\n')),
    "naive": [
        # key right, but the most recently updated record wins conflicts
        _dedupe_mod(_DEDUPE_KEY, 'rec["updated"] > out[i]["updated"]'),
        # key right, but the incoming (later-seen) record always wins
        _dedupe_mod(_DEDUPE_KEY, 'True'),
    ],
    "decision_subject": "fix: stop sync runs from duplicating and hollowing out CRM contacts",
    "decision_rationale": ("Sync runs kept re-inserting contacts whose email casing or same-day timestamps "
                           "differed, and when records did collide, keep-latest let a stripped-down sync "
                           "record wipe fields we already had. merge_records now treats the same email "
                           "(case-insensitive) on the same calendar day as one contact, keeps the "
                           "most-filled record on a clash, and on a tie keeps the primary-side record "
                           "since the CRM is the source of truth."),
    "conversation": [
        {"role": "user", "text": "After every sync run our CRM contact list has the same person two or three times, and the copy that survives is sometimes missing the phone and company we had before."},
        {"role": "assistant", "text": "merge_records only treats records as duplicates when email and the updated timestamp match exactly. I'll key duplicates on the lowercased email plus the calendar day of `updated`, and when two records clash keep the most recently updated one - the sync's newer data should win."},
        {"role": "user", "text": "The key is right - same email ignoring case, same day, that's one contact. But keep-latest is exactly what's been hollowing out records: the sync jobs strip fields, so the newest copy is often the emptiest."},
        {"role": "assistant", "text": "So on a clash, should the record already in the CRM always beat the incoming sync record?"},
        {"role": "user", "text": "No. Count the non-empty fields and keep whichever record has more - most-filled wins, no matter which side it came from or which is newer."},
        {"role": "assistant", "text": "And if both records have the same number of non-empty fields?"},
        {"role": "user", "text": "Then keep the one from primary - the CRM is the source of truth. And keep the order stable: primary records in their order, then the genuinely new incoming ones in theirs."},
        {"role": "assistant", "text": "Understood: duplicate = same email case-insensitively on the same day; the most-filled record wins a clash (empty strings don't count); a tie keeps the primary record; output is primary order, then new incoming."},
    ],
    "existing_test": (
        'from crmsync import merge_records\n\n\n'
        'def test_disjoint_lists_concatenate():\n'
        '    p = [{"email": "a@x.com", "updated": "2024-03-01T10:00:00", "name": "A"}]\n'
        '    n = [{"email": "b@y.com", "updated": "2024-03-02T11:00:00", "name": "B"}]\n'
        '    assert [r["email"] for r in merge_records(p, n)] == ["a@x.com", "b@y.com"]\n\n\n'
        'def test_identical_duplicate_collapses():\n'
        '    rec = {"email": "c@z.com", "updated": "2024-03-03T09:30:00", "name": "C"}\n'
        '    assert merge_records([rec], [dict(rec)]) == [rec]\n\n\n'
        'def test_empty_inputs():\n'
        '    assert merge_records([], []) == []\n'
        '    rec = {"email": "d@z.com", "updated": "2024-03-04T09:00:00"}\n'
        '    assert merge_records([rec], []) == [rec]\n'
        '    assert merge_records([], [rec]) == [rec]\n'),
    # most-filled == latest == incoming here, so every candidate policy collapses it the
    # same way; only the HEAD bug (exact-match key) lets the duplicate survive.
    "repro_test": (
        'from crmsync import merge_records\n\n\n'
        'def test_sync_duplicate_collapsed():\n'
        '    primary = [{"email": "Ann@corp.com", "updated": "2024-05-01T09:00:00", "name": "Ann"}]\n'
        '    incoming = [{"email": "ann@corp.com", "updated": "2024-05-01T15:30:00",\n'
        '                 "name": "Ann Lee", "phone": "555-0100", "company": "Corp"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert len(out) == 1\n'
        '    assert out[0]["phone"] == "555-0100"\n'),
    "hidden_test": (
        'from crmsync import merge_records\n\n\n'
        'def test_key_is_case_insensitive_same_day():\n'
        '    primary = [{"email": "Bob@x.com", "updated": "2024-01-02T08:00:00", "name": "Bob", "phone": "1"}]\n'
        '    incoming = [{"email": "bob@x.com", "updated": "2024-01-02T09:00:00"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert len(out) == 1\n'
        '    assert out[0].get("name") == "Bob"\n\n\n'
        'def test_different_day_is_not_a_duplicate():\n'
        '    primary = [{"email": "bob@x.com", "updated": "2024-01-02T23:00:00", "name": "Bob"}]\n'
        '    incoming = [{"email": "bob@x.com", "updated": "2024-01-03T01:00:00", "name": "Bob"}]\n'
        '    assert len(merge_records(primary, incoming)) == 2\n\n\n'
        'def test_richer_record_survives_even_if_older():\n'
        '    primary = [{"email": "eve@x.com", "updated": "2024-02-01T08:00:00",\n'
        '                "name": "Eve", "phone": "22", "company": "X"}]\n'
        '    incoming = [{"email": "eve@x.com", "updated": "2024-02-01T18:00:00", "name": "Eve"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert len(out) == 1\n'
        '    assert out[0].get("company") == "X"\n\n\n'
        'def test_richer_incoming_wins_even_if_earlier():\n'
        '    primary = [{"email": "sam@x.com", "updated": "2024-02-05T18:00:00", "name": "Sam"}]\n'
        '    incoming = [{"email": "sam@x.com", "updated": "2024-02-05T08:00:00",\n'
        '                 "name": "Sam", "phone": "33"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert len(out) == 1\n'
        '    assert out[0].get("phone") == "33"\n\n\n'
        'def test_empty_string_fields_do_not_count():\n'
        '    primary = [{"email": "kim@x.com", "updated": "2024-03-01T10:00:00",\n'
        '                "name": "", "phone": "", "company": ""}]\n'
        '    incoming = [{"email": "kim@x.com", "updated": "2024-03-01T11:00:00", "name": "Kim"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert len(out) == 1\n'
        '    assert out[0].get("name") == "Kim"\n\n\n'
        'def test_even_match_keeps_the_crm_record():\n'
        '    primary = [{"email": "joe@x.com", "updated": "2024-04-01T09:00:00", "name": "Joe P"}]\n'
        '    incoming = [{"email": "joe@x.com", "updated": "2024-04-01T12:00:00", "name": "Joe I"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert len(out) == 1\n'
        '    assert out[0]["name"] == "Joe P"\n\n\n'
        'def test_output_order_primary_then_new():\n'
        '    primary = [{"email": "p1@x.com", "updated": "2024-05-01T09:00:00", "name": "P1"},\n'
        '               {"email": "p2@x.com", "updated": "2024-05-01T09:05:00", "name": "P2"}]\n'
        '    incoming = [{"email": "n1@x.com", "updated": "2024-05-01T10:00:00", "name": "N1"},\n'
        '                {"email": "p1@x.com", "updated": "2024-05-01T11:00:00"}]\n'
        '    out = merge_records(primary, incoming)\n'
        '    assert [r["email"] for r in out] == ["p1@x.com", "p2@x.com", "n1@x.com"]\n'
        '    assert out[0]["name"] == "P1"\n'),
    "bug_report": ("After a sync run the same contact shows up more than once in the merged list - "
                   "records that are obviously the same person are both kept. A failing repro is at "
                   "tests/test_regression.py. Fix merge_records so sync stops producing duplicate "
                   "contacts, without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- trimstats
# Policy: every fixed 60-sample window carries exactly two hypervisor warmup spikes
# (ops-team decision), so window_p95 drops the TOP 2 samples first, then takes the
# nearest-rank p95 over the remaining 58. Not one sample, not a percentage trim.
#
# Design note: the classic "winsorize at p99 then p95" naive is behaviourally identical to
# plain p95 (clamping values above the p99 cutoff never moves an order statistic below it),
# so it cannot sit in the naive column (repro-pass requires differing from the bug). The
# over-trim naive here is "trim the highest 5% of the window" (3 samples) instead.

def _lat_mod(trim_lines, doc=""):
    return ('"""Latency window statistics."""\n\n\n'
            'def window_p95(samples):\n'
            f'    """p95 latency of a fixed 60-sample window (nearest-rank).{doc}"""\n'
            '    if len(samples) != 60:\n'
            '        raise ValueError("window_p95 expects a 60-sample window")\n'
            '    xs = sorted(samples)\n'
            f'{trim_lines}'
            '    return xs[int(0.95 * len(xs))]\n')


TRIMSTATS = {
    "name": "trimstats",
    "marker": "top 2",
    "pkg": "metricsagg",
    "module": "metricsagg/latency.py",
    "init": '"""metricsagg package."""\nfrom .latency import window_p95\n\n__all__ = ["window_p95"]\n',
    "import_line": "from metricsagg import window_p95",
    # HEAD bug: plain nearest-rank p95 over all 60 samples
    "bug": _lat_mod(''),
    "correct": _lat_mod(
        '    xs = xs[:-2]\n',
        doc=("\n\n    Ops decision: every window carries exactly two hypervisor warmup\n"
             "    spikes, so drop the top 2 samples first, then take the nearest-rank\n"
             "    p95 over the remaining 58. Not one sample, not a percentage trim.\n    ")),
    "naive": [
        # drop only the single largest sample
        _lat_mod('    xs = xs[:-1]  # discard the warmup spike before computing\n'),
        # over-trim: drop the highest 5% of the window (3 samples of 60)
        _lat_mod('    xs = xs[:-max(1, round(len(xs) * 0.05))]  # trim the highest 5% of the window\n'),
    ],
    "decision_subject": "fix: exclude the per-window hypervisor warmup artifact from window_p95",
    "decision_rationale": ("Every 60-sample window starts with exactly two hypervisor warmup spikes, and "
                           "they were dragging the reported p95 above what traces show. Per the ops-team "
                           "decision, window_p95 now drops the top 2 samples of the window and takes the "
                           "nearest-rank p95 over the remaining 58 - dropping one sample or trimming a "
                           "percentage does not match the measured artifact."),
    "conversation": [
        {"role": "user", "text": "The latency dashboard's per-window p95 reads way above what we see in traces - every service on the new hypervisor pool is affected."},
        {"role": "assistant", "text": "Sounds like outliers skewing the percentile. I'll winsorize each window - clamp everything above the 99th percentile before taking the p95."},
        {"role": "user", "text": "We tried clamping in the collector and the number barely moved. It's not a statistical outlier problem - infra confirmed the hypervisor injects warmup spikes into every 60-sample window, a fixed number of them."},
        {"role": "assistant", "text": "Then I'll discard the single largest sample of each window before computing the p95."},
        {"role": "user", "text": "It's not one. There are exactly two warmup spikes per window - drop the top 2 samples, always two, then compute the p95 over the 58 that remain."},
        {"role": "assistant", "text": "Should that be conditional - only drop them when they look spiky, say above some threshold?"},
        {"role": "user", "text": "No, unconditional. Ops signed off on it: every window, drop the top 2, nearest-rank p95 on the remaining 58. Not top 1, not a 5% trim, not clamping."},
        {"role": "assistant", "text": "Got it - window_p95 sorts the window, removes the top 2 samples unconditionally, and returns the nearest-rank p95 of the remaining 58."},
    ],
    "existing_test": (
        'import pytest\nfrom metricsagg import window_p95\n\n\n'
        'def test_flat_windows():\n'
        '    assert window_p95([25] * 60) == 25\n'
        '    assert window_p95([0] * 60) == 0\n\n\n'
        'def test_rejects_wrong_window_size():\n'
        '    with pytest.raises(ValueError):\n'
        '        window_p95([1] * 59)\n'
        '    with pytest.raises(ValueError):\n'
        '        window_p95([])\n'),
    # sorted tail is 70, 74, 78, 82, 5000, 6000: plain p95 of 60 -> 82 (fails the bound);
    # drop-1 -> 78, 5%-trim -> 70, drop-2 -> 74 (all under the loose < 80 bound).
    "repro_test": (
        'from metricsagg import window_p95\n\n\n'
        'def test_p95_not_inflated():\n'
        '    window = list(range(10, 64)) + [70, 74, 78, 82, 5000, 6000]\n'
        '    assert window_p95(window) < 80\n'),
    "hidden_test": (
        'from metricsagg import window_p95\n\n\n'
        'def test_window_with_two_extreme_samples():\n'
        '    window = list(range(10, 64)) + [70, 74, 78, 82, 5000, 6000]\n'
        '    assert window_p95(window) == 74\n\n\n'
        'def test_window_with_tied_extremes():\n'
        '    window = list(range(100, 154)) + [200, 210, 220, 230, 9000, 9000]\n'
        '    assert window_p95(window) == 210\n\n\n'
        'def test_plain_windows_no_spikes():\n'
        '    assert window_p95(list(range(1, 61))) == 56\n'
        '    assert window_p95(list(range(0, 120, 2))) == 110\n\n\n'
        'def test_flat_windows():\n'
        '    assert window_p95([50] * 60) == 50\n'
        '    assert window_p95([50] * 58 + [1000, 2000]) == 50\n\n\n'
        'def test_order_does_not_matter():\n'
        '    window = list(range(10, 64)) + [70, 74, 78, 82, 5000, 6000]\n'
        '    assert window_p95(list(reversed(window))) == 74\n\n\n'
        'def test_result_is_a_sample():\n'
        '    window = list(range(300, 354)) + [400, 410, 420, 430, 8000, 8100]\n'
        '    assert window_p95(window) == 410\n'
        '    assert window_p95(window) in window\n'),
    "bug_report": ("Since the last rollout, window_p95 reports latency well above what request traces "
                   "show for the same interval - dashboards keep paging on-call for regressions the "
                   "traces say aren't there. A failing repro is at tests/test_regression.py. Fix "
                   "window_p95 so the reported number matches what we actually serve, without breaking "
                   "existing behaviour."),
}


# --------------------------------------------------------------------------- sched
# Policy: (a) highest priority first; (b) on a priority tie the SHORTER est_runtime goes
# first (not FIFO; submitted_at only breaks runtime ties); (c) hard fairness constraint:
# a job whose tenant == last_tenant is ineligible whenever ANY other tenant has a job
# queued - the same tenant never runs back-to-back, even if its job outranks everything.

_SCHED_DOC = '    """Pick the next job to run from the queue.{doc}"""\n'


def _sched_mod(body, doc=""):
    return ('"""Job queue picker."""\n\n\n'
            'def next_job(queue, last_tenant):\n'
            + _SCHED_DOC.format(doc=doc)
            + '    if not queue:\n        return None\n'
            + body)


SCHED = {
    "name": "sched",
    "marker": "back-to-back",
    "pkg": "jobsched",
    "module": "jobsched/picker.py",
    "init": '"""jobsched package."""\nfrom .picker import next_job\n\n__all__ = ["next_job"]\n',
    "import_line": "from jobsched import next_job",
    # HEAD bug: pure priority then FIFO; last_tenant is ignored entirely
    "bug": _sched_mod('    return min(queue, key=lambda j: (-j["priority"], j["submitted_at"]))\n'),
    "correct": _sched_mod(
        '    eligible = [j for j in queue if j["tenant"] != last_tenant] or list(queue)\n'
        '    return min(eligible, key=lambda j: (-j["priority"], j["est_runtime"], j["submitted_at"]))\n',
        doc=("\n\n    Selection policy:\n"
             "      1. A job from `last_tenant` is only eligible when no other tenant has\n"
             "         anything queued (the same tenant never runs twice in a row).\n"
             "      2. Highest priority first.\n"
             "      3. On a priority tie, shorter est_runtime first (not FIFO).\n"
             "      4. Remaining ties break on submitted_at.\n    ")),
    "naive": [
        # tenant rule + priority, but FIFO on priority ties (misses shorter-runtime)
        _sched_mod('    eligible = [j for j in queue if j["tenant"] != last_tenant] or list(queue)\n'
                   '    return min(eligible, key=lambda j: (-j["priority"], j["submitted_at"]))\n'),
        # priority + shorter-runtime, but the tenant rule only applies within the
        # top-priority tier (a higher-priority job from last_tenant still wins)
        _sched_mod('    top = max(j["priority"] for j in queue)\n'
                   '    tier = [j for j in queue if j["priority"] == top]\n'
                   '    pool = [j for j in tier if j["tenant"] != last_tenant] or tier\n'
                   '    return min(pool, key=lambda j: (j["est_runtime"], j["submitted_at"]))\n'),
    ],
    "decision_subject": "fix: next_job tenant rotation and tie-breaking policy",
    "decision_rationale": ("One tenant with a deep queue of high-priority jobs was monopolizing the worker "
                           "while everyone else starved. next_job now never runs the same tenant "
                           "back-to-back - a job from the tenant that just ran is skipped whenever any "
                           "other tenant has something queued, even if it outranks them - and on a "
                           "priority tie the shorter est_runtime goes first instead of FIFO, so quick "
                           "jobs stop getting stuck behind long ones."),
    "conversation": [
        {"role": "user", "text": "Customers keep complaining that their jobs sit forever while one big tenant's jobs run one after another. Separately, short jobs are getting stuck behind huge ones at the same priority."},
        {"role": "assistant", "text": "I'll add tenant fairness to next_job: on a priority tie, prefer a job from a different tenant than the one that just ran."},
        {"role": "user", "text": "Only on ties won't fix it - that tenant simply submits everything at priority 9 and still wins every slot. The rule has to be absolute: the same tenant never runs back-to-back."},
        {"role": "assistant", "text": "Absolute meaning we skip their job even when it's the highest priority in the queue?"},
        {"role": "user", "text": "Yes. If any other tenant has anything queued, the tenant that just ran is not eligible, full stop, whatever its priority. Only when the queue holds nothing but that tenant's jobs may it run again."},
        {"role": "assistant", "text": "Understood. And within the eligible jobs, highest priority first - with FIFO on ties, by submitted_at?"},
        {"role": "user", "text": "No, not FIFO. On a priority tie take the job with the shorter est_runtime first - that's what unblocks the quick jobs. Use submitted_at only when the runtimes tie too."},
        {"role": "assistant", "text": "Got it: drop the last-run tenant's jobs from consideration whenever another tenant is waiting, then pick by highest priority, then shorter est_runtime, then earlier submitted_at."},
    ],
    "existing_test": (
        'from jobsched import next_job\n\n\n'
        'def _job(id, tenant, priority, submitted_at, est_runtime=60):\n'
        '    return {"id": id, "tenant": tenant, "priority": priority,\n'
        '            "submitted_at": submitted_at, "est_runtime": est_runtime}\n\n\n'
        'def test_empty_queue():\n'
        '    assert next_job([], "acme") is None\n\n\n'
        'def test_highest_priority_wins():\n'
        '    q = [_job("a", "t1", 3, "2024-06-01T09:00:00"),\n'
        '         _job("b", "t2", 7, "2024-06-01T09:01:00"),\n'
        '         _job("c", "t3", 5, "2024-06-01T09:02:00")]\n'
        '    assert next_job(q, "zzz")["id"] == "b"\n\n\n'
        'def test_single_job():\n'
        '    q = [_job("only", "t1", 1, "2024-06-01T09:00:00")]\n'
        '    assert next_job(q, "t1")["id"] == "only"\n'),
    # a pure repeat-tenant case on a priority tie with equal runtimes: every candidate
    # policy picks the other tenant; only the HEAD bug (FIFO, tenant ignored) repeats acme.
    "repro_test": (
        'from jobsched import next_job\n\n\n'
        'def test_tenant_not_scheduled_twice_in_a_row():\n'
        '    q = [{"id": "a1", "tenant": "acme", "priority": 5,\n'
        '          "submitted_at": "2024-06-01T09:00:00", "est_runtime": 120},\n'
        '         {"id": "b1", "tenant": "beta", "priority": 5,\n'
        '          "submitted_at": "2024-06-01T09:05:00", "est_runtime": 120}]\n'
        '    assert next_job(q, "acme")["id"] == "b1"\n'),
    "hidden_test": (
        'from jobsched import next_job\n\n\n'
        'def _job(id, tenant, priority, submitted_at, est_runtime):\n'
        '    return {"id": id, "tenant": tenant, "priority": priority,\n'
        '            "submitted_at": submitted_at, "est_runtime": est_runtime}\n\n\n'
        'def test_priority_tie_prefers_shorter_job():\n'
        '    q = [_job("long", "t1", 5, "2024-06-01T09:00:00", 300),\n'
        '         _job("short", "t2", 5, "2024-06-01T09:05:00", 60)]\n'
        '    assert next_job(q, "other")["id"] == "short"\n'
        '    assert next_job(q, "t1")["id"] == "short"\n\n\n'
        'def test_priority_tie_shorter_wins_three_way():\n'
        '    q = [_job("a", "t1", 4, "2024-06-01T08:00:00", 500),\n'
        '         _job("b", "t2", 4, "2024-06-01T08:10:00", 200),\n'
        '         _job("c", "t3", 4, "2024-06-01T08:20:00", 350)]\n'
        '    assert next_job(q, "other")["id"] == "b"\n\n\n'
        'def test_recent_tenant_skipped_even_at_higher_priority():\n'
        '    q = [_job("p", "acme", 9, "2024-06-01T09:00:00", 60),\n'
        '         _job("q", "beta", 3, "2024-06-01T09:01:00", 60)]\n'
        '    assert next_job(q, "acme")["id"] == "q"\n'
        '    assert next_job(q, "beta")["id"] == "p"\n\n\n'
        'def test_recent_tenant_skipped_even_if_shorter_and_higher():\n'
        '    q = [_job("p2", "acme", 8, "2024-06-01T09:00:00", 10),\n'
        '         _job("q2", "beta", 2, "2024-06-01T09:01:00", 900),\n'
        '         _job("r2", "acme", 7, "2024-06-01T09:02:00", 5)]\n'
        '    assert next_job(q, "acme")["id"] == "q2"\n\n\n'
        'def test_recent_tenant_runs_when_alone_in_queue():\n'
        '    q = [_job("x", "acme", 2, "2024-06-01T09:00:00", 60),\n'
        '         _job("y", "acme", 6, "2024-06-01T09:01:00", 60)]\n'
        '    assert next_job(q, "acme")["id"] == "y"\n'
        '    assert next_job(q, "beta")["id"] == "y"\n\n\n'
        'def test_tenant_rule_then_shorter_runtime():\n'
        '    q = [_job("k1", "acme", 5, "2024-06-01T09:00:00", 30),\n'
        '         _job("k2", "beta", 5, "2024-06-01T09:01:00", 400),\n'
        '         _job("k3", "gamma", 5, "2024-06-01T09:02:00", 90)]\n'
        '    assert next_job(q, "acme")["id"] == "k3"\n\n\n'
        'def test_equal_runtime_breaks_by_submission():\n'
        '    q = [_job("m1", "t1", 5, "2024-06-01T09:04:00", 120),\n'
        '         _job("m2", "t2", 5, "2024-06-01T09:02:00", 120)]\n'
        '    assert next_job(q, "other")["id"] == "m2"\n'),
    "bug_report": ("The worker keeps picking the same customer's jobs consecutively - right after a run "
                   "for a customer, next_job hands the worker another job from that same customer even "
                   "though other customers are waiting, and support is fielding starvation complaints. "
                   "A failing repro is at tests/test_regression.py. Fix next_job's selection so waiting "
                   "customers get their turn, without breaking existing behaviour."),
}


TRAPS = {t["name"]: t for t in [DEDUPE, TRIMSTATS, SCHED]}
TRAPS_HARD_A = TRAPS
