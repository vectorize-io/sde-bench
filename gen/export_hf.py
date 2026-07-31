#!/usr/bin/env python3
"""Export the dataset as a Hugging Face mirror (flat JSONL + dataset card).

The GitHub repo stays canonical (executable build.py, generator, validators); the Hub gets a flat,
`load_dataset()`-able representation: one row per task with everything needed to understand or
re-materialize it, plus the decoy-conversation pool as a second config. Re-running this script and
re-uploading is a clean override — the Hub repo is git, every push is a new commit on main, and
consumers can pin `revision=`.

Usage:
  python gen/export_hf.py                      # writes hf_export/ (tasks.jsonl, decoys.jsonl, README.md)
  python gen/export_hf.py --push <org>/sde-bench   # export + upload (needs `hf auth login` with write access)

Answer-leakage note: hidden_test is published (SWE-bench-style). Harnesses must never show it — or
anything derived from it — to the agent or its memory system.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from traps import TRAPS  # planted HEAD sources ride along so consumers can materialize without gen/

HOST_REPO = "https://github.com/vectorize-io/boltons"
HOST_REF = "979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe"


def task_rows() -> list[dict]:
    rows = []
    for tj in sorted(ROOT.glob("boltons-*/tasks/main/task.json")):
        t = json.loads(tj.read_text())
        d = tj.parent
        name = t["codebase"].replace("boltons-", "").replace("-history", "").replace("-amended", "")
        trap = TRAPS.get(name, {})
        rows.append({
            "task_id": t["task_id"],
            "codebase": t["codebase"],
            "source": t["source"],
            "tier": t["tier"],
            "category": t["category"],
            "module": t.get("module"),
            "function": t.get("function"),
            "policy": t.get("policy"),
            "non_guessable": t.get("non_guessable"),
            "bug_report": t["bug_report"],
            # decision material (exactly one of these families is populated, by source)
            "conversations": json.dumps(t.get("conversations")) if t.get("conversations") else None,
            "decision_subject": t.get("decision_subject"),
            "decision_rationale": t.get("decision_rationale"),
            "cause_subject": t.get("cause_subject"),
            # grading
            "fail_to_pass": json.dumps(t.get("fail_to_pass") or []),
            "pass_to_pass": json.dumps(t.get("pass_to_pass") or []),
            "hidden_to_pass": json.dumps(t.get("hidden_to_pass") or []),
            "regression_test": (d / t["regression_test_file"]).read_text(),
            "hidden_test": (d / t["hidden_test_file"]).read_text(),
            # materialization (planted tasks carry their HEAD module; real-function tasks are the
            # host file at host_ref, unmodified)
            "host_repo": HOST_REPO,
            "host_ref": HOST_REF,
            "planted_pkg": trap.get("pkg") if t["tier"] == "planted" else None,
            "planted_init": trap.get("init") if t["tier"] == "planted" else None,
            "head_module_source": trap.get("bug") if t["tier"] == "planted" else None,
        })
    return rows


def decoy_rows() -> list[dict]:
    decoys = json.loads((HERE / "decoy_conversations.json").read_text())
    return [{"id": d.get("id"), "topic": d.get("topic"), "turns": json.dumps(d.get("turns") or [])}
            for d in decoys]


CARD = """\
---
license: mit
task_categories:
- text-generation
language:
- en
tags:
- code
- agents
- memory
- benchmark
- swe
pretty_name: sde-bench
configs:
- config_name: tasks
  data_files: tasks.jsonl
  default: true
- config_name: decoys
  data_files: decoys.jsonl
---

# sde-bench — does memory help a coding agent?

{n_tasks} bug-fix tasks on a real codebase where every task hinges on a **non-guessable,
project-specific decision**: the obvious fix passes the visible repro test and fails a held-out
hidden test, because the project long ago decided the rule the obvious fix violates. The decision
lives in the repo's **git history** ({n_hist} tasks), a past **developer conversation**
({n_conv}), or a conversation later **amended** ({n_amend} — a cross-chat consolidation test).
Whether a memory system reliably surfaces it is what gets measured.

Every task is machine-validated to discriminate: HEAD fails repro+hidden, the correct fix passes
everything, and each of two plausible naive fixes passes the repro but fails hidden — guessing
cannot pass, knowing can.

- Canonical repo (executable tasks, generator, validators): https://github.com/vectorize-io/sde-bench
- Runner / harness / agents / grading: https://github.com/vectorize-io/agent-memory-benchmark
- Host fixture: [boltons](https://github.com/vectorize-io/boltons) @ `{host_ref_short}`
  (fork of [mahmoud/boltons](https://github.com/mahmoud/boltons), BSD, used unmodified)

## Configs

- **tasks** — one row per task: identity + axes (`source`, `tier`, `category`), the agent-facing
  `bug_report`, the decision material (`conversations` for chat sources; `decision_subject`/
  `decision_rationale` for history sources), the grading tests (`regression_test`, `hidden_test`,
  and the pass/fail file lists), and materialization fields (`host_repo`/`host_ref`, plus
  `head_module_source` for planted tasks).
- **decoys** — {n_decoys} realistic, policy-free developer conversations used as retrieval noise
  in every task's memory corpus.

⚠️ `hidden_test` is for **grading only** and must never reach the agent or its memory system.

## Quick start

```python
from datasets import load_dataset
tasks = load_dataset("{repo_id}", "tasks", split="train")
decoys = load_dataset("{repo_id}", "decoys", split="train")
```

To *run* the benchmark (build task repos, drive an agent, grade in Docker, count corrections),
use the runner in [agent-memory-benchmark](https://github.com/vectorize-io/agent-memory-benchmark):

```bash
uv run omb run --dataset sdebench --split boltons --mode coding --memory vanilla
uv run omb run --dataset sdebench --split boltons --mode coding --memory hindsight-coding
```

License: MIT (the sde-bench content — traps, planted modules, tests, conversations, decoys, and
this card). The boltons host fixture referenced at `host_repo`/`host_ref` is © Mahmoud Hashemi,
BSD-3-Clause, used unmodified.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "hf_export"))
    ap.add_argument("--push", default=None, help="<org>/<name> Hub dataset repo to upload to")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = task_rows()
    decoys = decoy_rows()
    (out / "tasks.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (out / "decoys.jsonl").write_text("\n".join(json.dumps(r) for r in decoys) + "\n")
    srcs = {}
    for r in rows:
        srcs[r["source"]] = srcs.get(r["source"], 0) + 1
    (out / "README.md").write_text(CARD.format(
        n_tasks=len(rows), n_hist=srcs.get("history", 0), n_conv=srcs.get("conversation", 0),
        n_amend=srcs.get("conversation-amended", 0), n_decoys=len(decoys),
        host_ref_short=HOST_REF[:7], repo_id=args.push or "<org>/sde-bench"))
    print(f"exported {len(rows)} tasks + {len(decoys)} decoys -> {out}")

    if args.push:
        from huggingface_hub import HfApi
        api = HfApi()
        api.create_repo(args.push, repo_type="dataset", exist_ok=True)
        api.upload_folder(folder_path=str(out), repo_id=args.push, repo_type="dataset",
                          commit_message=f"sde-bench export: {len(rows)} tasks, {len(decoys)} decoys")
        print(f"uploaded -> https://huggingface.co/datasets/{args.push}")


if __name__ == "__main__":
    main()
