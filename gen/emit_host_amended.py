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
