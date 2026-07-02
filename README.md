# sde-bench

**Does a coding agent benefit from a memory system?** A benchmark of bug-fix tasks whose correct
solution hinges on a **non-guessable, project-specific decision**: the obvious fix passes the visible
repro but fails a held-out hidden test. Where that decision *lives* — a real commit in the project's
git history (**H**) or a past developer conversation (**F**) — is the independent variable, and what a
memory system can *reach* is the point.

This repo is the **dataset** (10 tasks hosted in the real [boltons](https://github.com/mahmoud/boltons)
library). The runner/harness and the memory systems under test live in
[open-memory-benchmark](https://github.com/vectorize-io/open-memory-benchmark), which consumes this
repo as a git submodule.

## Layout

```
boltons-<name>/
  build.py                 # materializes the task's codebase (a boltons fork at 979fa9b)
  tasks/main/
    task.json              # metadata: source (H/F), tier, module/function, policy, tests, conversations
    regression_test.py     # the visible repro (red at HEAD)
    hidden_test.py         # the held-out test the naive fix fails
  tasks/oracle/            # (some tasks) an upper-bound arm
MANIFEST.json              # task index + counts
DATASET.md                 # datasheet: axes, tasks, grading, metric
DATASET_DESIGN.md          # design rationale
validate.py                # structural integrity check
```

## Validate

```bash
python validate.py     # checks every boltons-* task: required fields, tests parse, manifest consistency
```

## Use as a submodule

```bash
git submodule add https://github.com/vectorize-io/sde-bench.git <path>
```

See `DATASET.md` for the full datasheet (sources, tiers, grading, the interventions metric, and
results). boltons is © Mahmoud Hashemi, BSD, used unmodified as a fixture; the traps, planted modules,
tests, conversations, and datasheet are this project's.
