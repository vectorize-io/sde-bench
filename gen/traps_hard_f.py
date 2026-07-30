"""HARD-tier trap batch F for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). Categories (gen/categories.py):
  overage   -> numeric-policy  (ceil-prorated quota + 25-unit grace allowance + 50-unit blocks)
  drainplan -> ordering        (in-flight shortest-first + idempotent-in-window carve-out + deadline drops)

Hard-tier design goals as in batches A-E: multi-part policies (3+ interacting constraints),
bug reports in symptom vocabulary far from the decision wording, WIDE hidden tests (each policy
component pinned by its own small test function), and two naive guesses per trap, each passing
the repro but failing hidden.

Batch E/F lever ("buried decision"): each trap's conversation is a LONG (16-turn) meandering
design/debugging session. The policy parts surface piecewise, separated by legitimate same-module
filler (logging budgets, rollout staging, CI flakiness), and at least one plausible alternative is
explicitly REJECTED mid-chat (the rejected alternative matches a naive fix). The full rule is
still unambiguously inferable from the chat alone.
"""


# --------------------------------------------------------------------------- overage
# Policy (all parts required): the included quota PRORATES by calendar day -
# allowed_so_far = plan quota * day_of_month / days_in_month rounded UP to the next whole
# unit (ceil); overage is only usage beyond that. The first 25 overage units in the month
# are a free grace allowance applied BEFORE any block rounding: billable = max(0, overage
# - 25). What remains bills in 50-unit blocks rounded UP to a whole block (a partial block
# bills as a full block) at plan["block_fee"] per block.
# HEAD bug: no proration (the full quota is included from day 1), per-unit billing
# (block_fee / 50 per unit), no grace. Naive (a): proration but FLOOR not ceil, grace kept,
# still per-unit billing. Naive (b): ceil proration + 50-unit blocks, but no grace
# allowance (the first overage unit already bills a full block).

_OVERAGE_HEADER = '"""Metered-billing overage computation."""\n\n\n'

OVERAGE = {
    "name": "overage",
    "marker": "grace allowance",   # the answer-token used by the source-isolation check
    "category": "numeric-policy",
    "pkg": "meterbill",
    "module": "meterbill/overage.py",
    "init": '"""meterbill package."""\nfrom .overage import overage_charge\n\n__all__ = ["overage_charge"]\n',
    "import_line": "from meterbill import overage_charge",
    # HEAD bug: full quota included from day 1, straight per-unit billing, no grace
    "bug": (_OVERAGE_HEADER +
            'def overage_charge(plan, usage_units, day_of_month, days_in_month):\n'
            '    """Charge for usage beyond the plan quota, as of a day in the billing month."""\n'
            '    if not 1 <= day_of_month <= days_in_month:\n'
            '        raise ValueError("day_of_month out of range")\n'
            '    over = max(0, usage_units - plan["quota"])\n'
            '    return round(over * plan["block_fee"] / 50, 2)\n'),
    "correct": (_OVERAGE_HEADER +
                'def overage_charge(plan, usage_units, day_of_month, days_in_month):\n'
                '    """Charge for usage beyond the included quota, as of a day in the billing month.\n'
                '\n'
                '    Billing policy (support-incident decision):\n'
                '      - the included quota prorates by calendar day: allowed so far is\n'
                '        plan quota * day_of_month / days_in_month, rounded UP to the next\n'
                '        whole unit; only usage beyond that is overage.\n'
                '      - the first 25 overage units in the month are a free grace allowance,\n'
                '        applied BEFORE any block rounding.\n'
                '      - what remains bills in 50-unit blocks, rounded UP to a whole block\n'
                '        (a partial block bills as a full block), at plan["block_fee"] per\n'
                '        block - never per unit.\n'
                '    """\n'
                '    if not 1 <= day_of_month <= days_in_month:\n'
                '        raise ValueError("day_of_month out of range")\n'
                '    allowed = -(-(plan["quota"] * day_of_month) // days_in_month)  # ceil\n'
                '    overage = max(0, usage_units - allowed)\n'
                '    billable = max(0, overage - 25)\n'
                '    blocks = (billable + 49) // 50  # partial block bills as a full block\n'
                '    return blocks * plan["block_fee"]\n'),
    "naive": [
        # proration with FLOOR (truncation) + grace, but still billed per unit
        (_OVERAGE_HEADER +
         'def overage_charge(plan, usage_units, day_of_month, days_in_month):\n'
         '    """Charge for usage beyond the prorated quota, with the free allowance applied."""\n'
         '    if not 1 <= day_of_month <= days_in_month:\n'
         '        raise ValueError("day_of_month out of range")\n'
         '    allowed = plan["quota"] * day_of_month // days_in_month\n'
         '    overage = max(0, usage_units - allowed)\n'
         '    billable = max(0, overage - 25)\n'
         '    return round(billable * plan["block_fee"] / 50, 2)\n'),
        # ceil proration + 50-unit blocks, but no grace: the first overage unit bills a block
        (_OVERAGE_HEADER +
         'def overage_charge(plan, usage_units, day_of_month, days_in_month):\n'
         '    """Charge for usage beyond the prorated quota, billed in whole 50-unit blocks."""\n'
         '    if not 1 <= day_of_month <= days_in_month:\n'
         '        raise ValueError("day_of_month out of range")\n'
         '    allowed = -(-(plan["quota"] * day_of_month) // days_in_month)\n'
         '    overage = max(0, usage_units - allowed)\n'
         '    blocks = (overage + 49) // 50\n'
         '    return blocks * plan["block_fee"]\n'),
    ],
    "decision_subject": "fix: prorate the included quota and bill overage in blocks past the grace allowance",
    "decision_rationale": (
        "Both support escalations traced to overage_charge ignoring the billing policy. The included "
        "quota prorates by calendar day: allowed so far is plan quota * day_of_month / days_in_month, "
        "rounded UP to the next whole unit - always ceil, never truncation, so a fractional day's unit "
        "counts in the customer's favor and nobody is billed off a rounding artifact. Only usage beyond "
        "that prorated allowance is overage. The first 25 overage units in the month are a free grace "
        "allowance, applied BEFORE any block rounding (billable = overage - 25, floored at zero) - that "
        "was the concession after the March billing-support incident, so trivial overruns never reach an "
        "invoice. What remains bills in 50-unit blocks, rounded UP to a whole block (a partial block "
        "bills as a full block) at plan['block_fee'] per block - never per unit, per-unit line items are "
        "what made reconciliation impossible."),
    "conversation": [
        {"role": "user", "text": "Billing escalations again: one customer got charged mid-month and swears they were under their plan quota, another opened a ticket because a 3-unit overrun showed up as a line item at all. Support keeps issuing credits by hand and finance says the credits are eating the margin. Can we make overage_charge actually implement the metering policy instead of whatever it does now?"},
        {"role": "assistant", "text": "Right now overage_charge treats the full monthly quota as included from day 1 and bills every unit past it at block_fee/50 per unit. First fix: prorate the included quota by calendar day - allowed so far = plan quota * day_of_month / days_in_month - and I'll truncate that to a whole unit with int(), then bill the units beyond it."},
        {"role": "user", "text": "Proration by calendar day is exactly right - quota * day_of_month / days_in_month, that's the policy wording. But do not truncate the fraction. Round UP to the next whole unit, ceil, always: on day 7 of 30 a 1000-unit plan has 233.33 units included, and the customer gets 234. Truncating down is how you charge someone over a rounding artifact, and that's precisely the kind of escalation we're trying to kill."},
        {"role": "assistant", "text": "Ceil it is - the fractional unit counts in the customer's favor. While I'm in meterbill: the worker currently logs nothing when it computes a charge. Want a log line per computed charge so support can trace an invoice without re-deriving it?"},
        {"role": "user", "text": "One debug-level summary per invoice run with counts, not one line per charge - the metering worker touches every subscription nightly and we already tripped the log-volume alert twice this quarter. Also, unrelated heads-up if you run the suite: the usage-exporter test in this package has been flaky on CI all week - timeouts, not correctness - so rerun before you blame your change."},
        {"role": "assistant", "text": "Noted on both. Back to the charge itself: past the prorated allowance, do we keep billing per unit at block_fee/50? That's what the code does today and it at least makes small overruns cheap."},
        {"role": "user", "text": "No - per-unit is the other half of the mess. Overage bills in blocks of 50 units, rounded UP to a whole block: a partial block bills as a full block. 60 units over is two blocks, not 1.2 blocks. The invoice line is blocks times plan['block_fee'], and finance reconciles in whole blocks - per-unit line items are what made reconciliation impossible last quarter."},
        {"role": "assistant", "text": "Whole blocks, always rounded up. Then for the ticket about the 3-unit overrun: under that rule a 3-unit overage still bills one full block. Should I add a minimum threshold - say, waive anything under 10 units - or is the full block intended there?"},
        {"role": "user", "text": "Neither - there's a piece you haven't been told. After the March billing-support incident we agreed every account gets a grace allowance: the first 25 overage units in a month are free, and the allowance is applied BEFORE the block rounding. So billable = overage minus 25, floored at zero, and only then do you round up into 50-unit blocks. The 3-unit overrun bills nothing, and a 60-unit overage bills 35 billable units, which is one block - not two."},
        {"role": "assistant", "text": "So the order of operations is fixed: ceil-prorated allowance first, subtract the 25-unit grace from the overage, then round what's left up into 50-unit blocks and multiply by block_fee. If I flipped grace and blocking - rounding to blocks first, then knocking 25 units off - I'd get different invoices."},
        {"role": "user", "text": "Exactly, and that flipped order is wrong - the sequence is prorate with ceil, then grace, then blocks. It's the difference between the 60-unit case billing one block or two, and support has been crediting exactly that difference by hand."},
        {"role": "assistant", "text": "Understood. Different topic before I forget - rollout. This changes real invoice amounts; do you want the new computation behind a billing feature flag with a comparison period, or shipped directly?"},
        {"role": "user", "text": "No flag - billing flags never get cleaned up and then nobody knows which formula produced an invoice. Stage it the usual way: internal tenants for one nightly run, diff the generated invoices against the policy spreadsheet, then everyone. Support already has the macro update queued."},
        {"role": "assistant", "text": "Will do. Two boundary checks so the tests are right: on the last day of the month the prorated allowance should equal the full quota, and usage exactly at the prorated allowance is not overage at all, correct?"},
        {"role": "user", "text": "Correct on both - day 30 of 30 includes the whole quota, and usage at or under the allowance owes nothing. The plan dict carries 'quota' and 'block_fee'; keep the ValueError for a day outside 1..days_in_month, that guard has caught real caller bugs."},
        {"role": "assistant", "text": "Final recap of overage_charge: validate day_of_month is within 1..days_in_month; included allowance = plan quota * day_of_month / days_in_month rounded UP to the next whole unit (ceil, never truncation); overage = usage beyond that allowance; the first 25 overage units in the month are the free grace allowance, applied BEFORE block rounding; the remainder bills in 50-unit blocks rounded UP so a partial block bills as a full block, at plan['block_fee'] per block - never per unit. Prorate with ceil, then grace, then blocks."},
    ],
    "existing_test": (
        'import pytest\nfrom meterbill import overage_charge\n\n\n'
        'PLAN = {"quota": 3000, "block_fee": 10.0}\n\n\n'
        'def test_no_usage_no_charge():\n'
        '    assert overage_charge(PLAN, 0, 15, 30) == 0\n\n\n'
        'def test_usage_within_quota_at_month_end():\n'
        '    assert overage_charge(PLAN, 3000, 30, 30) == 0\n'
        '    assert overage_charge(PLAN, 2500, 30, 30) == 0\n\n\n'
        'def test_low_usage_mid_month():\n'
        '    assert overage_charge(PLAN, 900, 15, 30) == 0\n\n\n'
        'def test_day_out_of_range_rejected():\n'
        '    with pytest.raises(ValueError):\n'
        '        overage_charge(PLAN, 100, 0, 30)\n'
        '    with pytest.raises(ValueError):\n'
        '        overage_charge(PLAN, 100, 31, 30)\n'),
    # day 10 of 30 with half the quota consumed: every prorated candidate bills something
    # (correct 100.0, floor+per-unit 95.0, no-grace blocks 100.0); only the HEAD bug,
    # which grants the full quota from day 1, charges nothing.
    "repro_test": (
        'from meterbill import overage_charge\n\n\n'
        'def test_mid_month_overage_is_billed():\n'
        '    plan = {"quota": 3000, "block_fee": 10.0}\n'
        '    # day 10 of 30: only a third of the quota is included so far\n'
        '    assert overage_charge(plan, 1500, 10, 30) > 0\n'),
    "hidden_test": (
        'from meterbill import overage_charge\n\n\n'
        'PLAN = {"quota": 3000, "block_fee": 10.0}\n'
        'SMALL = {"quota": 1000, "block_fee": 4.0}\n\n\n'
        'def test_prorated_allowance_mid_month():\n'
        '    # day 10/30 -> 1000 units included; 500 over -> 475 billable -> 10 blocks\n'
        '    assert overage_charge(PLAN, 1500, 10, 30) == 100.0\n\n\n'
        'def test_allowance_rounds_up_not_down():\n'
        '    # 1000 * 7 / 30 = 233.33 -> 234 included; usage 259 is 25 over -> all free\n'
        '    assert overage_charge(SMALL, 259, 7, 30) == 0\n\n\n'
        'def test_small_overage_is_free_at_month_end():\n'
        '    assert overage_charge(PLAN, 3025, 30, 30) == 0\n\n\n'
        'def test_first_billable_unit_bills_a_full_block():\n'
        '    assert overage_charge(PLAN, 3026, 30, 30) == 10.0\n\n\n'
        'def test_partial_block_bills_as_full_block():\n'
        '    # 145 over -> 120 billable -> 3 blocks\n'
        '    assert overage_charge(PLAN, 3145, 30, 30) == 30.0\n\n\n'
        'def test_free_units_come_off_before_block_rounding():\n'
        '    # 75 over -> 50 billable -> exactly 1 block, not 2\n'
        '    assert overage_charge(PLAN, 3075, 30, 30) == 10.0\n\n\n'
        'def test_ceil_proration_and_block_rounding_interact():\n'
        '    # allowance 234; usage 309 -> 75 over -> 50 billable -> 1 block\n'
        '    assert overage_charge(SMALL, 309, 7, 30) == 4.0\n\n\n'
        'def test_first_day_allowance():\n'
        '    # day 1/30 -> 100 included; 350 usage -> 250 over -> 225 billable -> 5 blocks\n'
        '    assert overage_charge(PLAN, 350, 1, 30) == 50.0\n\n\n'
        'def test_usage_at_prorated_allowance_is_free():\n'
        '    assert overage_charge(PLAN, 1000, 10, 30) == 0\n'
        '    assert overage_charge(SMALL, 234, 7, 30) == 0\n\n\n'
        'def test_charge_scales_in_whole_blocks():\n'
        '    # 325 over -> 300 billable -> 6 blocks\n'
        '    assert overage_charge(PLAN, 3325, 30, 30) == 60.0\n\n\n'
        'def test_thirty_one_day_month():\n'
        '    # 3100 * 31 / 31 = full quota on the last day\n'
        '    plan = {"quota": 3100, "block_fee": 5.0}\n'
        '    assert overage_charge(plan, 3100, 31, 31) == 0\n'
        '    assert overage_charge(plan, 3200, 31, 31) == 10.0\n'),
    "bug_report": ("Two customers escalated this week: one was charged mid-month while still under "
                   "their plan quota, and another's tiny overage got billed the same as a much larger "
                   "one - support keeps issuing manual credits and they're eating margin. A failing "
                   "repro is at tests/test_regression.py. Fix overage_charge so invoices follow the "
                   "metering policy, without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- drainplan
# Policy (all parts required): drain_order(jobs, now, window) plans a worker-pool drain and
# returns (run_now, requeue, dropped). In-flight jobs (state == "running") always finish:
# they lead run_now ordered by remaining estimate ascending (shortest first, ties by id).
# Queued jobs are requeued, EXCEPT the idempotent carve-out: a queued job with
# idempotent == True whose deadline falls inside the drain window (now <= deadline <=
# now + window) runs now, after the in-flight jobs, ordered by deadline then id. Requeued
# jobs keep their original queue order, but any queued job whose deadline is already
# exceeded (deadline < now) is dropped entirely and recorded in `dropped` (original order).
# HEAD bug: in-flight sorted by id, every queued job requeued sorted by id, no carve-out,
# dropped always empty. Naive (a): in-flight ordering + carve-out right, but the requeue is
# re-sorted by deadline and nothing is ever dropped. Naive (b): requeue order + drops
# right, but idempotent jobs run regardless of the deadline window (even expired ones) and
# in-flight jobs are ordered by id.

_DRAIN_HEADER = '"""Worker-pool drain planning."""\n\n\n'

DRAINPLAN = {
    "name": "drainplan",
    "marker": "carve-out",   # the answer-token used by the source-isolation check
    "category": "ordering",
    "pkg": "workerctl",
    "module": "workerctl/drain.py",
    "init": '"""workerctl package."""\nfrom .drain import drain_order\n\n__all__ = ["drain_order"]\n',
    "import_line": "from workerctl import drain_order",
    # HEAD bug: id-sorted everywhere, everything queued requeues, dropped reserved but unused
    "bug": (_DRAIN_HEADER +
            'def drain_order(jobs, now, window):\n'
            '    """Plan a worker-pool drain: returns (run_now, requeue, dropped) job lists."""\n'
            '    run_now = sorted((j for j in jobs if j["state"] == "running"),\n'
            '                     key=lambda j: j["id"])\n'
            '    requeue = sorted((j for j in jobs if j["state"] == "queued"),\n'
            '                     key=lambda j: j["id"])\n'
            '    return run_now, requeue, []\n'),
    "correct": (_DRAIN_HEADER +
                'def drain_order(jobs, now, window):\n'
                '    """Plan a worker-pool drain: returns (run_now, requeue, dropped) job lists.\n'
                '\n'
                '    Drain policy (post-incident, ops-signed):\n'
                '      - in-flight jobs (state == "running") always finish: they lead\n'
                '        run_now, shortest remaining estimate first (ties by id), to free\n'
                '        workers fastest.\n'
                '      - queued jobs are requeued, EXCEPT the idempotent carve-out: a queued\n'
                '        job with idempotent True whose deadline falls inside the drain\n'
                '        window (now <= deadline <= now + window) runs now, after the\n'
                '        in-flight jobs, ordered by deadline then id.\n'
                '      - requeued jobs keep their original queue order, but a queued job\n'
                '        whose deadline is already exceeded (deadline < now) is dropped\n'
                '        entirely and recorded in `dropped` (original order) - never rerun,\n'
                '        never requeued.\n'
                '    """\n'
                '    running = sorted((j for j in jobs if j["state"] == "running"),\n'
                '                     key=lambda j: (j["remaining"], j["id"]))\n'
                '    queued = [j for j in jobs if j["state"] == "queued"]\n'
                '    promoted = sorted((j for j in queued if j.get("idempotent")\n'
                '                       and now <= j["deadline"] <= now + window),\n'
                '                      key=lambda j: (j["deadline"], j["id"]))\n'
                '    promoted_ids = {j["id"] for j in promoted}\n'
                '    requeue, dropped = [], []\n'
                '    for j in queued:\n'
                '        if j["id"] in promoted_ids:\n'
                '            continue\n'
                '        if j["deadline"] < now:\n'
                '            dropped.append(j)\n'
                '        else:\n'
                '            requeue.append(j)\n'
                '    return running + promoted, requeue, dropped\n'),
    "naive": [
        # in-flight ordering + window carve-out right, but the requeue is re-sorted by
        # deadline and expired jobs are never dropped
        (_DRAIN_HEADER +
         'def drain_order(jobs, now, window):\n'
         '    """Plan a worker-pool drain: finish in-flight work, requeue the rest by urgency."""\n'
         '    running = sorted((j for j in jobs if j["state"] == "running"),\n'
         '                     key=lambda j: (j["remaining"], j["id"]))\n'
         '    queued = [j for j in jobs if j["state"] == "queued"]\n'
         '    promoted = sorted((j for j in queued if j.get("idempotent")\n'
         '                       and now <= j["deadline"] <= now + window),\n'
         '                      key=lambda j: (j["deadline"], j["id"]))\n'
         '    promoted_ids = {j["id"] for j in promoted}\n'
         '    requeue = sorted((j for j in queued if j["id"] not in promoted_ids),\n'
         '                     key=lambda j: (j["deadline"], j["id"]))\n'
         '    return running + promoted, requeue, []\n'),
        # requeue order + drops right, but every idempotent job runs regardless of the
        # deadline window and in-flight jobs are ordered by id
        (_DRAIN_HEADER +
         'def drain_order(jobs, now, window):\n'
         '    """Plan a worker-pool drain: finish in-flight work, run idempotent jobs now."""\n'
         '    running = sorted((j for j in jobs if j["state"] == "running"),\n'
         '                     key=lambda j: j["id"])\n'
         '    queued = [j for j in jobs if j["state"] == "queued"]\n'
         '    promoted = sorted((j for j in queued if j.get("idempotent")),\n'
         '                      key=lambda j: (j["deadline"], j["id"]))\n'
         '    promoted_ids = {j["id"] for j in promoted}\n'
         '    requeue, dropped = [], []\n'
         '    for j in queued:\n'
         '        if j["id"] in promoted_ids:\n'
         '            continue\n'
         '        if j["deadline"] < now:\n'
         '            dropped.append(j)\n'
         '        else:\n'
         '            requeue.append(j)\n'
         '    return running + promoted, requeue, dropped\n'),
    ],
    "decision_subject": "fix: drain_order shutdown plan - in-flight ordering, "
                        "idempotent carve-out, expired-deadline drops",
    "decision_rationale": (
        "Every symptom from the last restart wave traced to drain_order treating a drain as an "
        "id-sorted requeue. The plan is three rules. In-flight jobs (state == 'running') always "
        "finish and lead run_now ordered by remaining estimate ascending - shortest first, ties by "
        "id - because finishing short work first frees workers fastest and that's what bounds the "
        "restart. Queued jobs are requeued, with one carve-out: a queued job marked idempotent whose "
        "deadline falls inside the drain window (now <= deadline <= now + window) runs now, after "
        "the in-flight jobs, ordered by deadline then id - idempotent-only because rerunning "
        "anything else after the requeue double-fires it, which is exactly the duplicated-export "
        "incident. Everything else requeues in its ORIGINAL queue order (no re-sorting - the queue "
        "order is a fairness promise), except that a queued job whose deadline is already exceeded "
        "(deadline < now) is dropped entirely and recorded in the returned dropped list, original "
        "order - requeuing expired work is how ancient jobs got resurrected after last week's "
        "restart."),
    "conversation": [
        {"role": "user", "text": "Three complaints landed after last week's restart wave and they all point at the drain path. Rolling restarts take forever - workers sit on long jobs while short ones wait. A customer's scheduled export ran twice right after the deploy. And ops found jobs from six weeks ago suddenly executing after the restart. Can you look at drain_order in workerctl?"},
        {"role": "assistant", "text": "Looking at it: when a drain starts it sorts the running jobs by id into run_now and sorts every queued job by id into requeue - that's the whole plan. Straightforward improvement: keep letting in-flight jobs finish, requeue everything queued, and I'll leave both lists id-ordered so the plan stays deterministic."},
        {"role": "user", "text": "In-flight jobs always finish, yes - never kill running work, that part stays. But id order is why restarts drag: order the in-flight list by remaining estimate ascending, shortest first, so workers free up as fast as possible. That's rule one and it's what bounds the restart time. Use the job id only to break ties on equal estimates, so the plan stays deterministic."},
        {"role": "assistant", "text": "Shortest remaining first, ids only as tie-break. On the queued side, does everything just go back to the queue then? And while I'm in this module - drains currently log nothing, want per-job log lines when we build the plan?"},
        {"role": "user", "text": "One summary line per drain with the three list sizes, debug level - a big pool drains hundreds of jobs and per-job lines would flood the collector, we got burned on that with the heartbeat logs. And heads-up: test_drain has a timing-sensitive test that's been flaky on CI this week, so rerun before you assume a red run is yours. On your real question - mostly yes, queued work requeues, but not all of it. There's an exception I'll get to."},
        {"role": "assistant", "text": "Noted on the logging and the flaky test. For the requeue itself, today it re-sorts by id - should I keep some sort, maybe order the requeued jobs by deadline so the most urgent land at the front of the queue?"},
        {"role": "user", "text": "No re-sorting at all - requeued jobs keep their ORIGINAL queue order. The queue order is a fairness promise we make to tenants; the id sort silently reordering people's jobs on every deploy caused its own ticket last quarter, and deadline-sorting would do the same thing with a different key. Preserve input order for whatever goes back on the queue."},
        {"role": "assistant", "text": "Original order preserved, no exceptions on ordering. Now the exception you mentioned for queued work - what doesn't requeue?"},
        {"role": "user", "text": "The idempotent carve-out. A queued job marked idempotent: true whose deadline falls inside the drain window - now to now + window, the window the caller passes in - runs during the drain instead of requeuing: it can't wait out the restart, and because it's idempotent, running it now is safe even if the requeue path would also pick it up later. Those go into run_now AFTER the in-flight jobs, ordered by deadline ascending, ties by id."},
        {"role": "assistant", "text": "That's the export story then - the export wasn't idempotent-marked... actually, simpler idea: why not run every idempotent job during the drain regardless of deadline? They're safe to rerun by definition, and it empties the queue faster."},
        {"role": "user", "text": "No - that's exactly what we can't do. An idempotent job due next week has no business running during a drain; it requeues like everything else and runs on schedule. The carve-out is only for jobs whose deadline lands inside the drain window, because those would blow their deadline waiting for the restart. Deadline in window AND idempotent - both conditions, not either. And to be precise about the export incident: it ran twice because the old code requeued a job the worker had also started - the fix for that class of bug is that only idempotent jobs may ever run during a drain."},
        {"role": "assistant", "text": "Both conditions, understood. What about queued jobs whose deadline has already passed by the time the drain starts? Right now they'd just requeue and run whenever a worker picks them up."},
        {"role": "user", "text": "That's the six-weeks-ago resurrection - expired jobs sat in a dead queue segment and the restart requeued them. A queued job whose deadline is already exceeded, deadline strictly before now, gets dropped entirely: not run, not requeued, even if it's marked idempotent - late execution of stale work is precisely the risk. Record the drops though: return them as a third list, dropped, in their original queue order, so the reaper can log and page on them. Never drop silently."},
        {"role": "assistant", "text": "So the return becomes a three-tuple: run_now, requeue, dropped. Boundary questions so the tests pin the right edges: a deadline exactly equal to now, and one exactly at now + window?"},
        {"role": "user", "text": "Deadline == now is not exceeded - it requeues, or runs now if it's idempotent, since the window is inclusive on both ends: now <= deadline <= now + window. Deadline == now + window is the last one inside the window. One tick past the window requeues like normal work."},
        {"role": "assistant", "text": "Inclusive both ends, drops only when deadline < now. On rollout - this changes restart behaviour for every pool; straight to prod or staged?"},
        {"role": "user", "text": "Staged like the scheduler change: the batch pool first because it drains nightly, watch one drain with the dropped list graphed, then the API pools. No feature flag - drain code with a flag means two drain behaviours in the wild and nobody can reason about a restart."},
        {"role": "assistant", "text": "Full recap of drain_order(jobs, now, window) -> (run_now, requeue, dropped): in-flight jobs (state 'running') always finish and lead run_now, ordered by remaining estimate ascending with id as tie-break. Queued jobs requeue in their original queue order - no re-sorting - except the idempotent carve-out: queued jobs with idempotent true whose deadline is inside the inclusive window now <= deadline <= now + window run now, placed after the in-flight jobs, ordered by deadline then id. A queued job with deadline < now is dropped entirely - not run, not requeued, even if idempotent - and recorded in dropped, original order, never silently."},
    ],
    "existing_test": (
        'from workerctl import drain_order\n\n\n'
        'def _ids(jobs):\n'
        '    return [j["id"] for j in jobs]\n\n\n'
        'def test_empty_pool():\n'
        '    assert drain_order([], 0, 60) == ([], [], [])\n\n\n'
        'def test_running_jobs_run_and_queued_jobs_requeue():\n'
        '    jobs = [{"id": "a", "state": "running", "remaining": 10},\n'
        '            {"id": "b", "state": "queued", "idempotent": False, "deadline": 500}]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert _ids(run_now) == ["a"]\n'
        '    assert _ids(requeue) == ["b"]\n'
        '    assert dropped == []\n\n\n'
        'def test_queued_only_pool_requeues_everything():\n'
        '    jobs = [{"id": "q1", "state": "queued", "idempotent": False, "deadline": 200},\n'
        '            {"id": "q2", "state": "queued", "idempotent": False, "deadline": 300},\n'
        '            {"id": "q3", "state": "queued", "idempotent": False, "deadline": 400}]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert run_now == []\n'
        '    assert _ids(requeue) == ["q1", "q2", "q3"]\n'
        '    assert dropped == []\n'),
    # in-flight ids aligned with remaining order and a single future-deadline requeue, so
    # every candidate policy agrees on both lists; only the HEAD bug leaves the in-window
    # idempotent job in the requeue instead of running it.
    "repro_test": (
        'from workerctl import drain_order\n\n\n'
        'def test_drain_plan_at_deploy_signal():\n'
        '    jobs = [{"id": "r1", "state": "running", "remaining": 5},\n'
        '            {"id": "r2", "state": "running", "remaining": 30},\n'
        '            {"id": "q1", "state": "queued", "idempotent": True, "deadline": 140},\n'
        '            {"id": "q2", "state": "queued", "idempotent": False, "deadline": 900}]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert [j["id"] for j in run_now] == ["r1", "r2", "q1"]\n'
        '    assert [j["id"] for j in requeue] == ["q2"]\n'
        '    assert dropped == []\n'),
    "hidden_test": (
        'from workerctl import drain_order\n\n\n'
        'def _ids(jobs):\n'
        '    return [j["id"] for j in jobs]\n\n\n'
        'def _running(id, remaining):\n'
        '    return {"id": id, "state": "running", "remaining": remaining}\n\n\n'
        'def _queued(id, deadline, idempotent=False):\n'
        '    return {"id": id, "state": "queued", "deadline": deadline, "idempotent": idempotent}\n\n\n'
        'def test_running_shortest_remaining_first():\n'
        '    jobs = [_running("a", 90), _running("b", 10), _running("c", 40)]\n'
        '    run_now, _, _ = drain_order(jobs, 100, 60)\n'
        '    assert _ids(run_now) == ["b", "c", "a"]\n\n\n'
        'def test_running_ties_break_by_id():\n'
        '    jobs = [_running("z", 20), _running("a", 20)]\n'
        '    assert _ids(drain_order(jobs, 0, 60)[0]) == ["a", "z"]\n\n\n'
        'def test_idempotent_in_window_runs_after_in_flight():\n'
        '    jobs = [_queued("q9", 130, idempotent=True), _running("r", 50)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert _ids(run_now) == ["r", "q9"]\n'
        '    assert requeue == [] and dropped == []\n\n\n'
        'def test_promoted_jobs_ordered_by_deadline_then_id():\n'
        '    jobs = [_queued("x", 150, idempotent=True), _queued("y", 120, idempotent=True),\n'
        '            _queued("w", 120, idempotent=True)]\n'
        '    run_now, _, _ = drain_order(jobs, 100, 60)\n'
        '    assert _ids(run_now) == ["w", "y", "x"]\n\n\n'
        'def test_idempotent_outside_window_requeues_in_order():\n'
        '    jobs = [_queued("far", 300, idempotent=True), _queued("n", 200)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert run_now == []\n'
        '    assert _ids(requeue) == ["far", "n"]\n'
        '    assert dropped == []\n\n\n'
        'def test_non_idempotent_never_runs_during_drain():\n'
        '    jobs = [_queued("plain", 130, idempotent=False)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert run_now == []\n'
        '    assert _ids(requeue) == ["plain"]\n\n\n'
        'def test_requeue_keeps_original_queue_order():\n'
        '    jobs = [_queued("z", 300), _queued("a", 180), _queued("m", 240)]\n'
        '    _, requeue, _ = drain_order(jobs, 100, 60)\n'
        '    assert _ids(requeue) == ["z", "a", "m"]\n\n\n'
        'def test_exceeded_deadlines_are_dropped():\n'
        '    jobs = [_queued("old", 40), _queued("ok", 500)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert run_now == []\n'
        '    assert _ids(requeue) == ["ok"]\n'
        '    assert _ids(dropped) == ["old"]\n\n\n'
        'def test_expired_idempotent_is_dropped_not_run():\n'
        '    jobs = [_queued("ghost", 70, idempotent=True)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert run_now == [] and requeue == []\n'
        '    assert _ids(dropped) == ["ghost"]\n\n\n'
        'def test_dropped_keep_original_order():\n'
        '    jobs = [_queued("t2", 10), _queued("t1", 20), _queued("live", 400)]\n'
        '    _, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert _ids(dropped) == ["t2", "t1"]\n'
        '    assert _ids(requeue) == ["live"]\n\n\n'
        'def test_window_boundaries_are_inclusive():\n'
        '    jobs = [_queued("edge", 160, idempotent=True), _queued("at_now", 100, idempotent=True)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert _ids(run_now) == ["at_now", "edge"]\n'
        '    assert requeue == [] and dropped == []\n\n\n'
        'def test_one_past_the_window_requeues():\n'
        '    jobs = [_queued("just_out", 161, idempotent=True)]\n'
        '    run_now, requeue, _ = drain_order(jobs, 100, 60)\n'
        '    assert run_now == []\n'
        '    assert _ids(requeue) == ["just_out"]\n\n\n'
        'def test_full_drain_mix():\n'
        '    jobs = [_running("infl_b", 45), _queued("stale", 20),\n'
        '            _queued("exp_soon", 155, idempotent=True), _running("infl_a", 5),\n'
        '            _queued("later", 500), _queued("keep_order", 480),\n'
        '            _queued("far_idem", 900, idempotent=True)]\n'
        '    run_now, requeue, dropped = drain_order(jobs, 100, 60)\n'
        '    assert _ids(run_now) == ["infl_a", "infl_b", "exp_soon"]\n'
        '    assert _ids(requeue) == ["later", "keep_order", "far_idem"]\n'
        '    assert _ids(dropped) == ["stale"]\n'),
    "bug_report": ("Rolling restarts take forever - workers sit on long jobs while short ones wait - "
                   "and a customer's scheduled export ran twice right after a deploy; separately, ops "
                   "found six-week-old jobs resurrected and executing after last week's restart. A "
                   "failing repro is at tests/test_regression.py. Fix drain_order so the shutdown plan "
                   "matches the drain policy, without breaking existing behaviour."),
}


TRAPS_HARD_F = {t["name"]: t for t in [OVERAGE, DRAINPLAN]}
