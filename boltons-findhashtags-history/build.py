import sys, os, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from realfn_traps import REALFN_TRAPS
from emit_realfn_h import H_MSG

_h = os.environ.get("SDEBENCH_BOLTONS_HOST")
if not _h:
    sys.exit("SDEBENCH_BOLTONS_HOST is required: git clone https://github.com/vectorize-io/boltons "
             "and point SDEBENCH_BOLTONS_HOST at the clone")
HOST = Path(os.path.expanduser(_h))
REF = '979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe'
T = REALFN_TRAPS['findhashtags']
SUBJ, BODY = H_MSG['findhashtags']
KEEP = set(['test_strutils.py']) | {"conftest.py", "__init__.py"}


def _commit(out, msg, author="Priya N."):
    subprocess.run(["git", "-C", str(out), "add", "-A"], check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": "p@e.com",
           "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": "p@e.com"}
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
    _commit(out, SUBJ + "\n\n" + BODY)
    # 2) regression: strip the policy back out (stock boltons), misleading message. HEAD is buggy.
    mod.write_text(src)
    _commit(out, "refactor: simplify " + Path(T["module"]).stem)
    print("built boltons-" + 'findhashtags' + "-h (H, real-function) @ " + REF[:8])


if __name__ == "__main__":
    main()
