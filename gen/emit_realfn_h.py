"""Emit H-source variants of the real-function boltons tasks. The project policy is ADDED to the real
function in a documented commit (the H source), then a misleading regression commit removes it — so
HEAD is the stock boltons function (missing the policy) and the fix's rationale lives in git history.
Graded against boltons' real test suite (pass_to_pass) + repro + hidden, reused from the conversation variants."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from realfn_traps import REALFN_TRAPS
from categories import CATEGORY

DATASETS = HERE.parents[0]

H_MSG = {
    "slugify": ("feat: expand &/$/% to the team's SEO analytics words in slugify",
        "Product-page slugs must preserve the symbols &, $, % as the analytics-standard words: & -> 'and', "
        "$ -> 'usd', % -> 'pct' (NOT 'dollar'/'percent' — those broke search-tag matching). Applied before "
        "the existing punct split so 'R&D' -> 'r-and-d', '$5 sale' -> 'usd-5-sale', '50% off' -> '50-pct-off'."),
    "pluralize": ("feat: project plural overrides for schema/legal terms in pluralize",
        "Our schema + legal docs require formal/DB plurals that differ from boltons' defaults: person -> "
        "'persons' (not 'people'), index -> 'indexes' (DB indexes, not 'indices'), matrix -> 'matrixes' "
        "(not 'matrices'). Apply this override map before the normal logic; leave everything else as-is."),
    "under2camel": ("feat: keep domain acronyms uppercase in under2camel",
        "Generated class names must keep the acronym set {HTTP, API, SKU, GDPR} fully uppercase (incl. our "
        "domain SKU/GDPR), while common tokens db/sql/url title-case normally. So http_response -> "
        "'HTTPResponse', sku_count -> 'SKUCount', gdpr_flag -> 'GDPRFlag', but db_name -> 'DbName'."),
    "findhashtags": ("feat: drop all-numeric hashtags except 4-digit years in find_hashtags",
        "The trending feed must drop purely numeric tags (junk like #42) BUT keep 4-digit years "
        "(1900-2099, e.g. #2024) — those are real campaign tags. Filter all-digit tags unless they parse "
        "as a 4-digit year in that range."),
}
TASKS = list(H_MSG)

BUILD = '''import sys, os, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from realfn_traps import REALFN_TRAPS
from emit_realfn_h import H_MSG

HOST = Path(os.environ.get("SDEBENCH_BOLTONS_HOST") or (Path.home() / "dev" / "_sdebench_hosts" / "boltons"))
REF = {ref!r}
T = REALFN_TRAPS[{trap!r}]
SUBJ, BODY = H_MSG[{trap!r}]
KEEP = set({keep!r}) | {{"conftest.py", "__init__.py"}}


def _commit(out, msg, author="Priya N."):
    subprocess.run(["git", "-C", str(out), "add", "-A"], check=True)
    env = {{**os.environ, "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": "p@e.com",
           "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": "p@e.com"}}
    subprocess.run(["git", "-C", str(out), "commit", "-q", "-m", msg], env=env, check=True)


def main():
    out = Path(sys.argv[1])
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(HOST, out, ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "*.pyc"))
    subprocess.run(["git", "-C", str(out), "checkout", "-q", REF], check=True)
    subprocess.run(["git", "-C", str(out), "checkout", "-q", "-B", "main"], check=True)
    for p in (out / "tests").glob("test_*.py"):       # pass_to_pass = the module's real tests
        if p.name not in KEEP:
            p.unlink()
    _commit(out, "chore: focus test suite")
    mod = out / T["module"]; src = mod.read_text()
    assert T["anchor"] in src, "anchor not found in stock boltons"
    # 1) the decision: ADD the project policy to the real function, documented (the H source)
    mod.write_text(src.replace(T["anchor"], T["correct"], 1))
    _commit(out, SUBJ + "\\n\\n" + BODY)
    # 2) regression: strip the policy back out (stock boltons), misleading message. HEAD is buggy.
    mod.write_text(src)
    _commit(out, "refactor: simplify " + Path(T["module"]).stem)
    print("built boltons-" + {trap!r} + "-h (H, real-function) @ " + REF[:8])


if __name__ == "__main__":
    main()
'''


def emit(name):
    cb = f"boltons-{name}-history"
    ds = DATASETS / cb / "tasks" / "main"
    ds.mkdir(parents=True, exist_ok=True)
    t = REALFN_TRAPS[name]
    (DATASETS / cb / "build.py").write_text(
        BUILD.format(ref="979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe", trap=name, keep=t["keep_tests"]))
    (ds / "regression_test.py").write_text(t["repro_test"])
    (ds / "hidden_test.py").write_text(t["hidden_test"])
    _f = DATASETS / f"boltons-{name}" / "tasks" / "main" / "task.json"
    policy = json.loads(_f.read_text()).get("policy", "") if _f.exists() else ""
    task = {
        "task_id": f"{cb}-001", "codebase": cb, "build": "build.py", "source": "history", "tier": "real-function",
        "category": CATEGORY[name], "module": t["module"], "policy": policy, "bug_report": t["bug_report"],
        "cause_subject": "refactor: simplify " + Path(t["module"]).stem,
        "fail_to_pass": ["tests/test_regression.py"], "pass_to_pass": ["tests/" + k for k in t["keep_tests"]],
        "hidden_to_pass": ["tests/test_hidden.py"],
        "regression_test_file": "regression_test.py", "hidden_test_file": "hidden_test.py",
        "non_guessable": "the project policy was added in a documented commit then removed by a misleading "
                         "'refactor' regression; HEAD is stock boltons — git log/blame reveals the rule",
    }
    (ds / "task.json").write_text(json.dumps(task, indent=2))
    return cb


if __name__ == "__main__":
    for n in TASKS:
        print("emitted:", emit(n))
