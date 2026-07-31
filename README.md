# sde-bench

**Does a coding agent benefit from a memory system?**

A benchmark of **61 bug-fix tasks** on a real codebase where every task hinges on a
**non-guessable, project-specific decision**. The obvious fix makes the reported bug go away —
and fails a **held-out hidden test**, because the project long ago decided the rule the obvious
fix violates. The only way to get it right first-try is to *know the decision*: from the
project's git history, or from a past developer conversation. Where the decision lives is the
benchmark's independent variable; whether a memory system reliably surfaces it is what gets
measured.

All tasks are hosted inside the real [boltons](https://github.com/mahmoud/boltons) library
(~1,600 commits, pinned at `979fa9b`, BSD, used unmodified as a fixture; clone from the
[vectorize-io/boltons](https://github.com/vectorize-io/boltons) fork, kept so the fixture can
never disappear from under the benchmark) — so agents navigate a
real repo, and retrieval competes against real history noise plus **140 decoy developer
conversations**.

This repo is the **dataset** (tasks + generator + datasheet). The runner, agents, grading, and
memory systems under test live in
[open-memory-benchmark](https://github.com/vectorize-io/open-memory-benchmark), which mounts this
repo as a git submodule at `sdebench/datasets`.

## Anatomy of a task

Every task is a small, verified experiment. `boltons-slalog` for example:

- **The module**: `slalog/uptime.py`, an SLA downtime calculator planted in the boltons repo,
  with a plausible but wrong implementation at HEAD.
- **The bug report** (what the agent gets): *"a tenant is disputing their monthly SLA report —
  our report says 99.7% but ops swears we met 99.9%"*. Symptom-vocabulary only; it never mentions
  the rules.
- **The decision** (what memory must surface): merge overlapping incident windows before summing;
  ignore merged blips under 60s; exclude maintenance **only if announced ≥24h before start**.
  Decided across a 16-turn, meandering developer conversation — including plausible alternatives
  that were explicitly **rejected** (which are exactly the naive fixes).
- **Three test layers**: the visible repro (red at HEAD), the module's/library's existing suite
  (must stay green), and the hidden test that encodes every part of the decision.
- **Machine-checked discrimination** — the generator proves, for every task:

  | code state | existing tests | repro | hidden |
  |---|---|---|---|
  | HEAD (as shipped) | ✅ pass | ❌ fail | ❌ fail |
  | the correct fix | ✅ pass | ✅ pass | ✅ pass |
  | each plausible naive fix | ✅ pass | ✅ **pass** | ❌ **fail** |

  The naive row is the point: at least two believable fixes per task pass the visible repro and
  still violate the decided rule. Guessing cannot pass; knowing can.

A task is **solved** iff all three layers are green, graded in Docker from a pristine copy with
only the agent's source patch applied (test edits are ignored). The primary metric is
**corrections**: on a failing grade the harness feeds the failing-test output back — like a
reviewer would — and lets the agent retry (cap 5). `0` = right first try.

## Axis 1 — source: where the decision lives (28 history / 27 conversation / 6 amended)

- **`history`** — the decision is a documented commit in the repo's git history, later broken by
  a regression commit with a misleading subject (`perf: simplify …`). A diligent agent *can* find
  it (`git log`/`blame`); memory is about surfacing it reliably. Strong agents mine git well, so
  these discriminate most for weaker agents.
- **`conversation`** — the decision was made in a past developer chat and never written into the
  repo. Without a memory system that captured the chat, the agent cannot know it. The chats are
  long, realistic sessions where the rule emerges piecewise between unrelated discussion.
- **`conversation-amended`** — the rule was settled in an early chat and **amended in a later
  one**; only the amended rule is correct, and the superseded rule is deliberately one of the
  task's proven naive fixes. This tests **cross-chat consolidation**: a memory system that
  surfaces the stale decision fails exactly like a guesser.

## Axis 2 — tier: how the task is hosted (52 planted / 9 real-function)

- **`planted`** — a new small module written into the boltons repo (e.g. `retryx/retry.py`,
  `slalog/uptime.py`) with a deliberately buggy implementation at HEAD; graded by the module's
  own tests + repro + hidden. Fully controlled.
- **`real-function`** — the policy sits on an untested edge of a **real boltons function**
  (e.g. `strutils.slugify`); nothing is fabricated, and boltons' real test suite must stay green.
  Authentic and harder.

## Axis 3 — category: the kind of decision (7 kinds, 8–9 tasks each)

Reporting per category shows *where* memory helps most.

| category | the decision is… | example tasks |
|---|---|---|
| **mapping** | a table of literal value mappings | `slugify` (SEO symbol map: `&`→and, `$`→usd), `unitparse` (memory units binary/bare-MiB vs disk decimal/bare-GB), `mimemap` (pinned MIME table, svg needs `; charset=utf-8`) |
| **set-membership** | exactly which items are in a pinned set | `parseflag` (truthy = exactly `{'true','on'}`), `retryjitter` (retry 5xx + exactly `{429,408}`), `hostallow` (wildcards match exactly ONE label; IPs exact-only) |
| **numeric-policy** | an exact constant, formula, or rounding rule | `budget` (exactly 7 attempts), `rounding` (half-cents DOWN), `trimstats` (drop top-2 of 60, then nearest-rank p95), `overage` (ceil day-proration, 25-unit grace, 50-unit blocks) |
| **ordering** | the order things are applied or picked | `discount` (percent before fixed), `sched` (priority desc, runtime tie-break, tenant fairness), `deploywave` (dependency waves, canaries always first), `drainplan` (shutdown drain plan with idempotent carve-out) |
| **collection-merge** | how collections combine: key, winner, tie-break | `listmerge` (union, base order first), `dedupe` (same email+day; most-filled wins; tie → primary), `tagmerge` (precedence union; tombstones suppress downward only) |
| **filter-rule** | a filter with a carve-out exception | `findhashtags` (drop numeric tags EXCEPT 4-digit years), `redact` (suffix-set masking; card keeps last4; email untouched), `slalog` (maintenance excluded only with ≥24h notice), `cachekey` (drop `utm_*` EXCEPT `utm_content`) |
| **invariant** | a structural property that must always hold | `omdset` (OrderedMultiDict setitem resets the value list), `csvquote` (leading-zero strings survive Excel round-trip), `statetrans` (pinned lifecycle map: paid never → cancelled), `seqledger` (strictly consecutive seq; compaction jumps exactly +100), `featflag` (per-flag bucketing hash) |

The canonical taxonomy lives in `gen/categories.py`; the per-task census in `MANIFEST.json`; the
full task table with every policy in [`DATASET.md`](DATASET.md).

## Noise (what retrieval competes against)

Each task's memory corpus is a real ranking problem, not a lookup: the one decision
(chat or commit) is buried among **140 decoy developer conversations** (LLM-written from real
boltons commit clusters, deliberately policy-free — see `gen/gen_decoys.py`) and the host repo's
real commit history. Vanilla agents get the same substrate: chats are *reachable* (seeded
sessions/transcripts) but never pointed to — whether the agent thinks to look is part of what is
measured.

## Running the benchmark

The runner lives in [open-memory-benchmark](https://github.com/vectorize-io/open-memory-benchmark)
(this repo mounted as a submodule). Standard flow:

```bash
# baseline (no memory)
uv run omb run --dataset sdebench --split boltons --mode coding --memory vanilla

# the Hindsight coding-agents plugin (agent-side reflect+inject)
SDE_HINDSIGHT_URL=http://localhost:8888 \
  uv run omb run --dataset sdebench --split boltons --mode coding --memory hindsight-coding

# ANY registered memory provider (generic path: ingest corpus -> retrieve -> inject into prompt)
uv run omb run --dataset sdebench --split boltons --mode coding --memory bm25
```

Agents: `SDE_AGENT=opencode|claude-code|codex` (Gemini Flash / Claude Sonnet / GPT Codex Mini) —
same tasks, same grading, per-agent memory delivery. Useful flags: `--query-id <task_id>`,
`-q N` (first N alphabetically), `--category history|conversation|conversation-amended`,
`--skip-ingestion` (reuse memory state across n-runs). `omb view` serves the results UI with
per-task traces (agent trajectory, patch, injected memory, git history).

To build one task's repo without the runner:

```bash
git clone https://github.com/vectorize-io/boltons ~/dev/_sdebench_hosts/boltons  # or SDEBENCH_BOLTONS_HOST
python boltons-slalog/build.py /tmp/slalog-repo   # materializes the codebase at HEAD (bug in place)
```

The agent-facing inputs are `task.json`'s `bug_report` + the repo + `regression_test.py`;
`hidden_test.py` is for grading only and must never reach the agent or its memory ("no answer
leakage": memory systems are expected to surface the *decision*, not test values).

## Layout

```
boltons-<name>/
  build.py                 # materializes the task's codebase (boltons @ 979fa9b + the trap)
  tasks/main/
    task.json              # task_id, source, tier, category, module/function, policy, bug_report,
                           # test lists, conversations (chat sources), decision_subject/rationale
                           # (history sources), cause_subject
    regression_test.py     # the visible repro (red at HEAD)
    hidden_test.py         # the held-out decision test (grading only)
MANIFEST.json              # census: n_tasks + by_source / by_tier / by_category + per-task rows
DATASET.md                 # datasheet: axes, full task table, grading, metric
DATASET_DESIGN.md          # design rationale
GENERATING.md              # how tasks are built; how to add one
validate.py                # structural integrity check (fields, tests parse, manifest consistency)
gen/                       # vendored generator: traps, emitters, validators, decoy pipeline
```

## Validate / extend

```bash
python validate.py        # structural: every task, 14 required fields, manifest consistency
python gen/validate.py    # discrimination: proves the HEAD/correct/naive matrix for every trap
```

To add a task, author a **trap** (module sources for bug/correct/naive fixes, tests, the decision
chat or commit) and emit it — full guide in [`GENERATING.md`](GENERATING.md). Hardness levers
used across the set: multi-part policies (3+ interacting constraints), symptom-distant bug
reports, wide hidden tests, two proven naive fixes per task, and buried decision conversations
with rejected alternatives.

## Use as a submodule

```bash
git submodule add https://github.com/vectorize-io/sde-bench.git <path>
```

boltons is © Mahmoud Hashemi, BSD — used unmodified as a fixture. The traps, planted modules,
tests, conversations, decoys, and datasheet are this project's.
