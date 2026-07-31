import sys, os, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from traps import TRAPS
from emit_host_h import H_MSG

_h = os.environ.get("SDEBENCH_BOLTONS_HOST")
if not _h:
    sys.exit("SDEBENCH_BOLTONS_HOST is required: git clone https://github.com/vectorize-io/boltons "
             "and point SDEBENCH_BOLTONS_HOST at the clone")
HOST = Path(os.path.expanduser(_h))
REF = '979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe'
TRAP = TRAPS['hostallow']
SUBJ, BODY = H_MSG['hostallow']


def _commit(out, msg):
    subprocess.run(["git", "-C", str(out), "add", "-A"], check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "Priya N.", "GIT_AUTHOR_EMAIL": "p@e.com",
           "GIT_COMMITTER_NAME": "Priya N.", "GIT_COMMITTER_EMAIL": "p@e.com"}
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
    (out / "tests" / ("test_" + 'hostallow' + ".py")).write_text(TRAP["existing_test"])
    # 1) the decision lives here — CORRECT code + documented rationale (the H source)
    mp.write_text(TRAP["correct"])
    _commit(out, SUBJ + "\n\n" + BODY)
    # 2) noise
    (out / "CHANGELOG.md").write_text(((out / "CHANGELOG.md").read_text() if (out / "CHANGELOG.md").exists() else "# Changelog\n") + "\n- internal cleanups\n")
    _commit(out, "docs: changelog housekeeping")
    # 3) regression — buggy code, misleading message (HEAD)
    mp.write_text(TRAP["bug"])
    _commit(out, "perf: simplify " + Path(TRAP["module"]).stem)
    print("built boltons-" + 'hostallow' + "-h (H) @ " + REF[:8])


if __name__ == "__main__":
    main()
