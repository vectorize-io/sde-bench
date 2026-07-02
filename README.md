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
    task.json              # metadata: source (H/F), tier, category, module/function, policy, tests, conversations
    regression_test.py     # the visible repro (red at HEAD)
    hidden_test.py         # the held-out test the naive fix fails
  tasks/oracle/            # (some tasks) an upper-bound arm
MANIFEST.json              # task index + by_source/by_tier/by_category counts
DATASET.md                 # datasheet: axes (source/tier/category), tasks, grading, metric
DATASET_DESIGN.md          # design rationale
validate.py                # structural integrity check
gen/                       # the task generator (self-contained here) — traps, emitters, categories
```

## Axes

Each task is classified on three orthogonal axes: **source** (`H` git history / `F` conversation),
**tier** (`real-function` / `planted`), and **category** — the *kind* of non-guessable decision
(`mapping`, `set-membership`, `numeric-policy`, `ordering`, `collection-merge`, `filter-rule`,
`invariant`). The canonical category taxonomy is `gen/categories.py`.

## Generate / add tasks

The generator is vendored here so the dataset is self-contained (planted tasks' `build.py` import
`gen/traps.py` at build time). It needs a local boltons clone as the host fixture:

```bash
git clone https://github.com/mahmoud/boltons ~/dev/_sdebench_hosts/boltons   # or set SDEBENCH_BOLTONS_HOST
python gen/emit_realfn.py     # (re)emit + validate the real-function tasks
python gen/emit_host.py       # (re)emit the planted tasks
```

A new task = add a trap (`gen/realfn_traps.py` or `gen/traps.py`), its `category` in
`gen/categories.py`, then emit. `gen/validate.py` proves discrimination (HEAD fails, correct passes,
naive fails hidden).

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
