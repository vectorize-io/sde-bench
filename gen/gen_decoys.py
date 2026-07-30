#!/usr/bin/env python3
"""Generate a large pool of DECOY developer conversations from the boltons git history — long,
realistic, codebase-related, but unrelated to any task decision. These are retrieval NOISE: they make
the chat/F memory a real ranking problem (1 real decision chat buried among many plausible decoys),
instead of the trivial "only one chat in the bank" case.

Idea (user's): mine real commits, cluster them by the file/module they touch, and for each cluster ask
an LLM to write a multi-turn dev conversation *about that area of the code* — design discussion,
debugging, trade-offs — WITHOUT stating any of the benchmark's planted policies. Deterministic-ish and
generated ONCE into decoy_conversations.json (reused across every task bank), so it's cheap at run time.

Usage: uv run python sdebench/datasets/gen/gen_decoys.py [--n 60] [--out decoy_conversations.json]
Env: GEMINI_API_KEY. Host clone at ~/dev/_sdebench_hosts/boltons (or SDEBENCH_BOLTONS_HOST).
"""
import argparse, json, os, subprocess, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = Path(os.environ.get("SDEBENCH_BOLTONS_HOST") or (Path.home() / "dev" / "_sdebench_hosts" / "boltons"))
REF = "979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe"

# never let a decoy leak a planted task's answer vocabulary — steer generation away from these modules.
# Keep in sync with the trap files (traps.py + traps_hard_*.py): every planted module basename plus
# the real-function host modules.
TASK_MODULES = {"strutils.py", "dictutils.py", "rounding.py", "retry.py", "discount.py", "flags.py",
                "merge.py", "dedupe.py", "latency.py", "picker.py", "redact.py", "policy.py",
                "writer.py", "uptime.py", "units.py", "transitions.py", "waves.py",
                "tags.py", "ledger.py", "overage.py", "drain.py"}

PROMPT = """You are writing a REALISTIC internal developer conversation for a code-history corpus. It is
about the `{file}` area of the `boltons` Python utility library, grounded in these real commits:

{commits}

Write a natural multi-turn conversation (6-12 turns, alternating user/assistant) between two engineers
discussing THIS part of the codebase — design rationale, a refactor, a subtle bug, a trade-off, testing,
or a perf question. Make it specific and technical, referencing real function/class names from the
commit subjects. It should read like a genuine Slack/PR thread: sometimes rambling, a wrong idea first,
then a resolution.

HARD RULES:
- This is NOISE for a memory benchmark. Do NOT state any concrete "project policy" of the form "X must
  be exactly Y" (no specific rounding modes, retry counts, symbol maps, acronym sets, truthy sets,
  list-merge rules, plural overrides). Keep it about general engineering discussion, not a pinned rule.
- Do NOT invent a decision another team must follow verbatim. It's a discussion, not a spec.
- Return ONLY JSON: {{"topic": "<short topic>", "turns": [{{"role":"user","text":"..."}}, ...]}}
"""


def commit_clusters(limit_files: int, per_file: int, commits: int) -> list[tuple[str, list[str]]]:
    """Group the last `commits` commits by the top-level module file they touch; return
    [(file, [commit lines])]. Scoped to the same commit window the backfill ingests (default 100)."""
    US = "\x1f"
    log = subprocess.run(
        ["git", "-C", str(HOST), "log", f"-n{commits}", f"--format=%h{US}%s", "--name-only", REF],
        capture_output=True, text=True).stdout
    by_file: dict[str, list[str]] = defaultdict(list)
    cur = None
    for line in log.splitlines():
        if US in line:
            cur = line.split(US, 1)  # [sha, subject]
        elif line.strip().endswith(".py") and cur:
            f = line.strip().split("/")[-1]
            if f in TASK_MODULES:  # skip task-touched modules entirely
                continue
            by_file[f].append(f"{cur[0]} {cur[1]}")
    # >=2 commits per module so a small window (100) still yields a decent decoy pool
    clusters = [(f, cs[:per_file]) for f, cs in by_file.items() if len(cs) >= 2]
    clusters.sort(key=lambda kv: -len(kv[1]))
    return clusters[:limit_files]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="target number of decoy conversations")
    ap.add_argument("--commits", type=int, default=100, help="commit window to mine (match backfill git-limit)")
    ap.add_argument("--out", default=str(HERE / "decoy_conversations.json"))
    ap.add_argument("--model", default="gemini-2.5-flash")
    args = ap.parse_args()

    sys.path.insert(0, str(HERE.parents[2] / "src"))
    from google import genai
    client = genai.Client()

    clusters = commit_clusters(limit_files=args.n, per_file=8, commits=args.commits)
    print(f"[decoys] {len(clusters)} commit clusters (by module); generating up to {args.n} conversations …")
    out = []
    for i, (f, commits) in enumerate(clusters[:args.n]):
        prompt = PROMPT.format(file=f, commits="\n".join("- " + c for c in commits))
        try:
            resp = client.models.generate_content(model=args.model, contents=prompt)
            txt = resp.text.strip()
            if txt.startswith("```"):
                txt = txt.split("```")[1].lstrip("json").strip()
            conv = json.loads(txt)
            if conv.get("turns"):
                conv["id"] = f"decoy-{f.replace('.py','')}-{i}"
                out.append(conv)
                if (i + 1) % 10 == 0:
                    print(f"  {len(out)} generated …")
        except Exception as e:
            print(f"  ! cluster {f} failed: {str(e)[:100]}")
    Path(args.out).write_text(json.dumps(out, indent=1))
    n_turns = sum(len(c["turns"]) for c in out)
    print(f"[decoys] wrote {len(out)} decoy conversations ({n_turns} turns) -> {args.out}")


if __name__ == "__main__":
    main()
