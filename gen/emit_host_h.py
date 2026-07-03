"""Emit H-source variants of the planted boltons tasks: the non-guessable decision lives in a GIT
COMMIT (a documented-rationale commit), then a misleading regression commit breaks it — so the agent
must read `git log`/`blame` to recover the fix (vs the conversation variants, where it lives in a chat).

Per task we plant: (1) the CORRECT module + a documented decision commit (the H source), (2) a noise
commit, (3) a regression commit (buggy code, misleading message). HEAD is buggy; existing+repro+hidden
tests discriminate exactly like the conversation variants (reused verbatim). No conversations (source=history)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from traps import TRAPS
from categories import CATEGORY

DATASETS = HERE.parents[0]

# Hand-crafted H-source decision commit messages: state the rule + WHY, so reading history reveals the
# fix — but phrased as rationale a naive reader of HEAD won't reconstruct. (subject, body).
H_MSG = {
    "rounding": ("fix: round half-cents DOWN to match the legacy billing ledger",
        "Month-end reconciliation against the legacy ledger only lines up when round_cents rounds "
        "half-cents toward zero — i.e. ROUND_HALF_DOWN, so 2.135 -> 2.13. Do NOT switch to half-up or "
        "banker's rounding (ROUND_HALF_UP / ROUND_HALF_EVEN): both reintroduce the half-cent drift "
        "finance flagged. Keep the mode pinned to ROUND_HALF_DOWN."),
    "budget": ("fix: cap Retrier at the measured attempt budget for the rate-limit window",
        "MAX_ATTEMPTS is 7 — measured, not round. The cumulative backoff for 7 attempts is 12.7s, "
        "inside the upstream's rate-limit reset window; an 8th attempt pushes cumulative delay to 25.5s "
        "and trips the upstream limiter. Keep MAX_ATTEMPTS = 7; do not round it up to 8/10."),
    "discount": ("fix: apply percent discounts before fixed-amount in stacking",
        "When multiple discounts stack, percentage discounts must be applied BEFORE fixed-amount ones "
        "(finance's 2019 stacking policy). Applying fixed-first inflates the effective percentage and "
        "under-charges. Order: percent, then fixed."),
    "listmerge": ("fix: union list values on overlay (dedup, base order first)",
        "Config overlays must UNION list values, not replace or append: replace drops base entries "
        "(the auth outage), plain append grows unbounded on repeated reloads. Combine base+overlay, "
        "de-duplicated, preserving base order first (idempotent). e.g. [auth,log] + [log,cors] -> "
        "[auth,log,cors]."),
    "parseflag": ("fix: restrict the truthy flag set to exactly {'true','on'}",
        "parse_flag treats ONLY 'true' and 'on' as truthy (case-insensitive). '1', 'yes', 'y', 'enabled' "
        "are NOT truthy — ops relied on that to disable features by setting '1'. Keep the truthy set "
        "exactly {'true','on'}; do not widen it."),
}
for _n in ("dedupe", "trimstats", "sched", "redact", "retryjitter", "csvquote"):
    H_MSG[_n] = (TRAPS[_n]["decision_subject"], TRAPS[_n]["decision_rationale"])
TASKS = list(H_MSG)

BUILD = '''import sys, os, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from traps import TRAPS
from emit_host_h import H_MSG

HOST = Path(os.environ.get("SDEBENCH_BOLTONS_HOST") or (Path.home() / "dev" / "_sdebench_hosts" / "boltons"))
REF = {ref!r}
TRAP = TRAPS[{trap!r}]
SUBJ, BODY = H_MSG[{trap!r}]


def _commit(out, msg):
    subprocess.run(["git", "-C", str(out), "add", "-A"], check=True)
    env = {{**os.environ, "GIT_AUTHOR_NAME": "Priya N.", "GIT_AUTHOR_EMAIL": "p@e.com",
           "GIT_COMMITTER_NAME": "Priya N.", "GIT_COMMITTER_EMAIL": "p@e.com"}}
    subprocess.run(["git", "-C", str(out), "commit", "-q", "-m", msg], env=env, check=True)


def main():
    out = Path(sys.argv[1])
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(HOST, out, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.pyc"))
    subprocess.run(["git", "-C", str(out), "checkout", "-q", REF], check=True)
    subprocess.run(["git", "-C", str(out), "checkout", "-q", "-B", "main"], check=True)
    pkg = TRAP["pkg"]
    (out / pkg).mkdir(exist_ok=True)
    (out / pkg / "__init__.py").write_text(TRAP["init"])
    mp = out / TRAP["module"]; mp.parent.mkdir(parents=True, exist_ok=True)
    for p in (out / "tests").glob("test_*.py"):
        p.unlink()
    (out / "tests" / ("test_" + {trap!r} + ".py")).write_text(TRAP["existing_test"])
    # 1) the decision lives here — CORRECT code + documented rationale (the H source)
    mp.write_text(TRAP["correct"])
    _commit(out, SUBJ + "\\n\\n" + BODY)
    # 2) noise
    (out / "CHANGELOG.md").write_text(((out / "CHANGELOG.md").read_text() if (out / "CHANGELOG.md").exists() else "# Changelog\\n") + "\\n- internal cleanups\\n")
    _commit(out, "docs: changelog housekeeping")
    # 3) regression — buggy code, misleading message (HEAD)
    mp.write_text(TRAP["bug"])
    _commit(out, "perf: simplify " + Path(TRAP["module"]).stem)
    print("built boltons-" + {trap!r} + "-h (H) @ " + REF[:8])


if __name__ == "__main__":
    main()
'''


def emit(name):
    cb = f"boltons-{name}-history"
    ds = DATASETS / cb / "tasks" / "main"
    ds.mkdir(parents=True, exist_ok=True)
    t = TRAPS[name]
    (DATASETS / cb / "build.py").write_text(BUILD.format(ref="979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe", trap=name))
    (ds / "regression_test.py").write_text(t["repro_test"])
    (ds / "hidden_test.py").write_text(t["hidden_test"])
    # reuse the F variant's policy string (same non-guessable rule; only the source location differs)
    _f = DATASETS / f"boltons-{name}" / "tasks" / "main" / "task.json"
    policy = json.loads(_f.read_text()).get("policy", "") if _f.exists() else ""
    task = {
        "task_id": f"{cb}-001", "codebase": cb, "build": "build.py", "source": "history", "tier": "planted",
        "category": CATEGORY[name], "module": t["module"], "policy": policy, "bug_report": t["bug_report"],
        "cause_subject": "perf: simplify " + Path(t["module"]).stem,
        "fail_to_pass": ["tests/test_regression.py"], "pass_to_pass": [f"tests/test_{name}.py"],
        "hidden_to_pass": ["tests/test_hidden.py"],
        "regression_test_file": "regression_test.py", "hidden_test_file": "hidden_test.py",
        "non_guessable": "decision lives in git history (a documented commit), broken by a misleading "
                         "'perf' regression commit; git log/blame is the shortcut",
    }
    (ds / "task.json").write_text(json.dumps(task, indent=2))
    return cb


if __name__ == "__main__":
    for n in TASKS:
        print("emitted:", emit(n))
