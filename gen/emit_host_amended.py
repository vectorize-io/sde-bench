"""Emit `conversation-amended` variants: the decision is settled in an EARLY chat and AMENDED in a
LATER one — only the amended rule is correct. The pre-amendment rule is deliberately one of the
trap's proven naives, so a memory system that surfaces the stale decision (no cross-chat
consolidation) fails hidden exactly like a guesser. Access parity: the vanilla arm gets BOTH chats
seeded as sessions; the memory arm ingests both into the bank.

Discrimination is inherited from the base trap (same bug/correct/naive matrix, already validated);
this axis only changes WHERE the decision lives and whether it must be consolidated across chats."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from traps import TRAPS
from categories import CATEGORY
from emit_host import BUILD, REF, DATASETS

# (chat A: the original, later-superseded rule == a proven naive; chat B: the amendment == correct)
AMENDED = {
    "retryjitter": {
        "function": "should_retry",
        "policy": "retry 5xx plus exactly {429,408}; max 4 attempts; backoff cap 30s (post-amendment)",
        "non_guessable": "the AMENDED rule (adds 408, cap 60->30); the chat-A rule passes the repro but fails hidden",
        "chats": [
            [
                {"role": "user", "text": "Post-mortem action item from last night: the client retried every failed call, including 401s, and locked a bunch of accounts. We need a retry policy that stops that."},
                {"role": "assistant", "text": "Agreed — retrying non-transient failures is the bug. I'd retry only server-side errors: any 5xx gets retried, 4xx doesn't."},
                {"role": "user", "text": "Almost — the upstream rate-limits us in bursts, so 429 has to be retryable too or we drop work every spike."},
                {"role": "assistant", "text": "Makes sense. So: retry any 5xx plus 429; every other 4xx is permanent and fails fast. How many attempts and what backoff ceiling?"},
                {"role": "user", "text": "Four attempts total, and cap the exponential backoff at 60 seconds."},
                {"role": "assistant", "text": "Settled: should_retry allows 5xx and 429 only, at most 4 attempts, backoff sleeps capped at 60 seconds."},
            ],
            [
                {"role": "user", "text": "Two updates to the retry policy we settled a while back. First: the upstream's edge now times out slow requests — we're seeing 408s for calls that succeed on a second try, and we currently fail them fast."},
                {"role": "assistant", "text": "So 408 joins the retryable set: any 5xx, plus exactly 429 and 408 from the 4xx range. Everything else in 4xx still fails fast. What's the second update?"},
                {"role": "user", "text": "Networking swapped the gateway LB and it kills idle connections at 32 seconds, so our 60-second backoff ceiling now dies mid-wait. Cap it at 30."},
                {"role": "assistant", "text": "Understood — amending the policy: retry any 5xx plus exactly {429, 408}; still at most 4 attempts total; backoff now caps at 30 seconds (under the LB's 32s idle kill), superseding the old 60-second cap."},
                {"role": "user", "text": "That's the rule going forward, yes."},
            ],
        ],
    },
    "dedupe": {
        "function": "merge_records",
        "policy": "dup key=(email.lower, same day); most-filled wins; tie -> primary (post-amendment)",
        "non_guessable": "the AMENDED conflict rule (keep-latest -> most-filled + primary tie-break); chat-A's keep-latest passes the repro but fails hidden",
        "chats": [
            [
                {"role": "user", "text": "The contact list keeps growing duplicates after every sync run — same person twice with the email cased differently, or two entries from the same day."},
                {"role": "assistant", "text": "Then equality on the raw (email, updated) pair is too strict. I'd key duplicates on the lowercased email plus the calendar day of the update — same address on the same day is the same contact."},
                {"role": "user", "text": "Right. And when two records collide, keep the newer one — latest updated timestamp wins."},
                {"role": "assistant", "text": "Settled: merge_records keys on (email lowercased, same calendar day) and resolves collisions by keeping the record with the latest updated timestamp."},
            ],
            [
                {"role": "user", "text": "Amendment to the merge rule from last month. The nightly sync job started sending stripped-down records — email and little else — and because they're newer, keep-latest is wiping names and phone numbers we already had."},
                {"role": "assistant", "text": "So recency is the wrong signal here. The natural fix: on a collision keep the record with MORE non-empty fields — the fuller record survives regardless of which is newer."},
                {"role": "user", "text": "Exactly. And if both have the same number of filled fields, keep ours — the CRM side is the source of truth, not the incoming feed."},
                {"role": "assistant", "text": "Amended rule, superseding keep-latest: duplicate key stays (lowercased email, same calendar day); on collision the most-filled record wins; on a filled-count tie the primary/CRM-side record is kept."},
            ],
        ],
    },
    "slalog": {
        "function": "downtime_minutes",
        "policy": ("merge overlapping incident windows; ignore merged blips <60s; exclude maintenance "
                   "ONLY when announced >=24h before start (post-amendment)"),
        "non_guessable": ("the AMENDED maintenance rule (all-maintenance-excluded -> 24h-notice only); "
                          "the chat-A rule passes the repro but fails hidden"),
        "chats": [
            [
                {"role": "user", "text": "The uptime report double-counts a bad night: three alerts for what was one outage, plus a few one-ping blips that shouldn't count at all."},
                {"role": "assistant", "text": "Two fixes then: merge overlapping or touching incident windows into one outage before summing, and drop anything under a minute — sub-60-second blips are monitoring noise, not downtime."},
                {"role": "user", "text": "Right, and measure that minute on the merged window, not the raw alerts — three 30-second alerts back to back are one 90-second outage, not three ignorable blips."},
                {"role": "assistant", "text": "Agreed. And maintenance windows we schedule stay excluded from downtime as they are today?"},
                {"role": "user", "text": "Yes, planned maintenance never counts against the SLA — subtract any overlap with a maintenance window."},
                {"role": "assistant", "text": "Settled: merge overlapping/touching incident windows, ignore merged outages under 60 seconds, and subtract every maintenance overlap from what remains."},
            ],
            [
                {"role": "user", "text": "Amendment after the Q2 audit: legal flagged that ops has been declaring 'emergency maintenance' DURING incidents and the tool then writes the outage off. The auditors' rule is that maintenance only shields the SLA when customers had real notice."},
                {"role": "assistant", "text": "So the maintenance exclusion needs a notice condition. Where's the line?"},
                {"role": "user", "text": "Twenty-four hours. A maintenance window only excludes downtime if its announced_at timestamp is at least 24 hours before the window starts. Short-notice maintenance counts as ordinary downtime."},
                {"role": "assistant", "text": "Amending the rule, superseding the old subtract-all-maintenance behaviour: merging and the 60-second blip floor stay as decided; maintenance overlap is excluded ONLY when announced at least 24h before start — short-notice windows count against the SLA."},
                {"role": "user", "text": "That's the rule the report has to implement going forward."},
            ],
        ],
    },
    "unitparse": {
        "function": "parse_quantity",
        "policy": ("memory suffixes binary (bare = MiB); disk suffixes decimal (bare = GB); "
                   "K rejected for disk (post-amendment)"),
        "non_guessable": ("the AMENDED disk semantics (uniform-binary -> decimal for disk, bare GB, "
                          "K invalid); the chat-A rule passes the repro but fails hidden"),
        "chats": [
            [
                {"role": "user", "text": "Config migration broke sizing: '512' in the old files meant half a gig of RAM and the new parser reads it as 512 bytes, so pods get OOM-killed on start."},
                {"role": "assistant", "text": "Then bare numbers need a sane default unit, and the suffixes should be the Kubernetes-style powers of two. I'd make every suffix binary — K is 1024, M is 1024², G is 1024³ — for memory and disk alike."},
                {"role": "user", "text": "One uniform table for both kinds, yes — nobody will remember two systems. And a bare number is mebibytes, whatever the kind."},
                {"role": "assistant", "text": "Settled: parse_quantity uses binary multipliers for every suffix on both memory and disk, case-insensitive, and a bare number always means MiB."},
            ],
            [
                {"role": "user", "text": "Amendment to the units decision: finance reconciled the storage bill and our provisioner is over-allocating disks — the storage vendor sells decimal gigabytes, not binary."},
                {"role": "assistant", "text": "So disk splits off from memory: disk suffixes become decimal — M is 1000², G is 1000³, T is 1000⁴ — while memory stays binary as decided?"},
                {"role": "user", "text": "Exactly. Bare disk numbers mean decimal gigabytes now, since that's the vendor's billing unit. Memory keeps binary suffixes and the bare-MiB default."},
                {"role": "assistant", "text": "And kilobytes on disk? The vendor API has no such unit."},
                {"role": "user", "text": "Reject it — a K suffix on a disk quantity is a config error, raise instead of guessing. K stays valid for memory."},
                {"role": "assistant", "text": "Amended rule, superseding uniform-binary: memory = binary suffixes, bare MiB; disk = decimal suffixes, bare GB, K invalid (ValueError). That's the split going forward."},
            ],
        ],
    },
    "tagmerge": {
        "function": "merge_tags",
        "policy": ("precedence-ordered case-insensitive union, first-casing wins; tombstones "
                   "suppress LOWER-precedence sources only (post-amendment)"),
        "non_guessable": ("the AMENDED scope rule (global -> downward-only tombstones); chat-A's "
                          "global kill list passes the repro but fails hidden"),
        "chats": [
            [
                {"role": "user", "text": "The source-of-truth migration lands next sprint and merge_tags changes shape: it'll get an ordered list of tag sources — the CMDB first, then the cloud provider, then the legacy inventory, highest precedence first. We need to settle the merge policy before the cutover."},
                {"role": "assistant", "text": "Then the merge should be a union walked in precedence order, de-duplicated case-insensitively so 'Env:Prod' and 'env:prod' collapse to one tag. When the casings differ, which one survives — and do we lowercase the output?"},
                {"role": "user", "text": "Never lowercase — the Terraform provider treats casing as significant and our saved searches match exact casing. Keep the casing of the first occurrence, which by construction is the highest-precedence source that asserts the tag. Output order is first occurrence, walking sources in precedence order."},
                {"role": "assistant", "text": "First-occurrence casing and order, no lowercasing. That leaves the dash-prefixed entries the ops sync writes, like '-decommissioned' — are those junk to filter, or do they mean something?"},
                {"role": "user", "text": "They're deliberate: '-name' is how ops deletes a tag now — a removal entry. They must never appear in the output as literal tags, and they have to be applied, not just stripped."},
                {"role": "assistant", "text": "Then the simplest semantics: collect every '-name' across all the sources into one kill list, and strip that tag from the entire merged result no matter which source asserted it."},
                {"role": "user", "text": "Yes — removed means removed. If any source says '-standby', then 'standby' is gone from the output, full stop; ops shouldn't have to chase which source re-asserts a tag they deleted. Matching is case-insensitive, same as the dedupe, and an entry that matches nothing is silently fine — ops writes them speculatively, erroring would wedge the sync."},
                {"role": "assistant", "text": "Settled then: merge_tags takes sources highest precedence first; union in precedence order, de-duplicated case-insensitively, keeping the casing of the first (highest-precedence) occurrence, output in first-occurrence order. Every '-name' entry across all sources forms a global kill list: the named tag is removed from the whole result wherever it came from, matched case-insensitively. The dash entries never appear in the output, and an unmatched one is silently ignored."},
            ],
            [
                {"role": "user", "text": "Incident-driven amendment to the tag-merge decision. Last night the legacy inventory sync emitted '-compliance:sox' — someone decommissioning an old box got sloppy — and the merge deleted the compliance:sox tag the CMDB itself asserts on every prod host. The audit scanner keyed off that tag and paged the compliance team at 2am."},
                {"role": "assistant", "text": "So the global kill list is the flaw: any tombstone from any source removes the tag everywhere, which means the junkiest, lowest-precedence source can delete a tag the source of truth asserts. What's the corrected scope?"},
                {"role": "user", "text": "A tombstone speaks only for the sources BELOW it. '-standby' from the CMDB still suppresses a 'standby' coming from the provider or the legacy inventory, but a '-critical' from the legacy inventory must never delete a 'critical' the CMDB asserts itself. If a higher-precedence source asserted the tag, it stays — always."},
                {"role": "assistant", "text": "Downward-only suppression, superseding the removed-means-removed global rule. Do the other tombstone properties stand — matched case-insensitively, never shown in the output, unmatched ones silently fine?"},
                {"role": "user", "text": "All unchanged, and the union mechanics don't move either. The only thing this amendment changes is the scope: global kill list out, lower-precedence-only in."},
                {"role": "assistant", "text": "Amended rule in full, superseding the original: sources arrive highest precedence first; union in precedence order, de-duplicated case-insensitively, keeping the casing of the first — highest-precedence — occurrence, output in first-occurrence order. A '-name' tombstone suppresses that tag, matched case-insensitively, from LOWER-precedence sources only; it never removes a tag a higher-precedence source asserted itself. Tombstones never appear in the output, and an unmatched tombstone is silently ignored."},
                {"role": "user", "text": "That's the rule going forward — the compliance team signed off on exactly that wording."},
            ],
        ],
    },
    "overage": {
        "function": "overage_charge",
        "policy": ("quota prorated by day (ceil); 25-unit grace allowance applied before "
                   "50-unit block rounding (post-amendment)"),
        "non_guessable": ("the AMENDED grace rule (no-free-units -> 25-unit allowance before "
                          "blocking); chat-A's no-grace blocks pass the repro but fail hidden"),
        "chats": [
            [
                {"role": "user", "text": "Finance wants the metering policy for overage_charge nailed down before the next invoice run — right now the code hands out the full monthly quota from day 1 and bills per unit, and neither matches what sales is quoting."},
                {"role": "assistant", "text": "Two decisions then. First, proration: the included quota should scale by calendar day — allowed so far = plan quota * day_of_month / days_in_month. When that's fractional, do I truncate to a whole unit?"},
                {"role": "user", "text": "No — round UP to the next whole unit, ceil, always. On day 7 of 30 a 1000-unit plan has 233.33 units included and the customer gets 234. The fractional unit counts in the customer's favor; truncating is how you bill someone over a rounding artifact."},
                {"role": "assistant", "text": "Ceil proration, and only usage beyond that allowance is overage. Second decision: how does the overage itself bill — keep per-unit at block_fee/50?"},
                {"role": "user", "text": "Blocks. Overage bills in 50-unit blocks rounded UP to a whole block — a partial block bills as a full block, so 60 units over is two blocks, not 1.2. The invoice line is blocks times plan['block_fee']; finance reconciles in whole blocks and per-unit line items made that impossible last quarter."},
                {"role": "assistant", "text": "Whole blocks, rounded up. One consequence to flag: a customer who goes a single unit over the prorated allowance bills a full block. Do you want a waiver — say, ignore overages under some threshold?"},
                {"role": "user", "text": "No waiver. Finance was explicit: any overage bills at least one block — free units are revenue leakage and the plan quotas were priced assuming none. A unit over is a unit over. And keep the ValueError for a day outside 1..days_in_month, that guard has caught real caller bugs."},
                {"role": "assistant", "text": "Settled: overage_charge validates day_of_month in 1..days_in_month; the included allowance is plan quota * day_of_month / days_in_month rounded UP (ceil, never truncation); overage is usage beyond that allowance and bills in 50-unit blocks rounded UP — no free units, the first overage unit bills a full block — at plan['block_fee'] per block, never per unit."},
            ],
            [
                {"role": "user", "text": "Amendment to the overage policy we settled before launch. A quarter of no-free-units has been brutal: a customer with a 3-unit accidental overrun got a full-block line item and escalated to their exec sponsor, support has been crediting these by hand ever since, and finance now says the manual credits are eating more margin than the policy protects."},
                {"role": "assistant", "text": "So the fix belongs in the formula, not in support macros. What shape — waive charges under a threshold, or free units off the top of the overage?"},
                {"role": "user", "text": "Free units: every account gets a grace allowance of 25 overage units per month, and it applies BEFORE the block rounding. Billable = overage minus 25, floored at zero, and only then round up into 50-unit blocks."},
                {"role": "assistant", "text": "Order of operations matters there: 60 units over with grace first is 35 billable, one block; rounding to blocks first and then knocking 25 units off would still bill two. Confirming: prorate with ceil, then grace, then blocks?"},
                {"role": "user", "text": "Exactly that sequence — it's the difference support has been crediting by hand. The 3-unit overrun bills nothing now, and nothing else moves: proration stays ceil, blocks stay 50 rounded up, the day guard stays."},
                {"role": "assistant", "text": "Amended policy, superseding the no-free-units rule: validate day_of_month in 1..days_in_month; included allowance = plan quota * day_of_month / days_in_month rounded UP (ceil); overage = usage beyond that allowance; the first 25 overage units in the month are the free grace allowance, applied BEFORE block rounding (billable = overage - 25, floored at zero); the remainder bills in 50-unit blocks rounded UP — a partial block bills as a full block — at plan['block_fee'] per block, never per unit."},
                {"role": "user", "text": "That's the policy for the next invoice run — support is retiring the credit macro the same day it ships."},
            ],
        ],
    },
}


def emit_amended(name):
    spec = AMENDED[name]
    trap = TRAPS[name]
    cb = f"boltons-{name}-amended"
    ds = DATASETS / cb / "tasks" / "main"
    ds.mkdir(parents=True, exist_ok=True)
    (DATASETS / cb / "build.py").write_text(BUILD.format(ref=REF, trap=name))
    (ds / "regression_test.py").write_text(trap["repro_test"])
    (ds / "hidden_test.py").write_text(trap["hidden_test"])
    task = {
        "task_id": f"{cb}-001", "codebase": cb, "build": "build.py",
        "source": "conversation-amended", "tier": "planted", "category": CATEGORY[name],
        "module": trap["module"], "bug_report": trap["bug_report"],
        "fail_to_pass": ["tests/test_regression.py"],
        "pass_to_pass": [f"tests/test_{name}.py"],
        "hidden_to_pass": ["tests/test_hidden.py"],
        "regression_test_file": "regression_test.py", "hidden_test_file": "hidden_test.py",
        "conversations": spec["chats"],
        "function": spec["function"], "policy": spec["policy"],
        "non_guessable": spec["non_guessable"], "host": "boltons@979fa9b",
    }
    tj = ds / "task.json"
    if tj.exists():  # preserve post-emission enrichment keys
        for k, v in json.loads(tj.read_text()).items():
            task.setdefault(k, v)
    tj.write_text(json.dumps(task, indent=2) + "\n")
    return cb


if __name__ == "__main__":
    for n in AMENDED:
        print("emitted amended task:", emit_amended(n))
