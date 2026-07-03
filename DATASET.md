# sdebench-boltons — datasheet

A benchmark for **whether a coding agent, working on a real codebase, benefits from a memory system**
that has ingested the project's git history and past developer conversations.

Each task is a bug-fix whose correct solution hinges on a **non-guessable, project-specific decision**.
The obvious fix passes the visible repro but fails a held-out test. Where that decision *lives* is the
independent variable — and what each agent can *reach* is the whole point.

## What each arm can access (this is the experiment)

| | plain agent | agent + memory |
|---|---|---|
| the repo + its full git history | ✅ | ✅ |
| a memory store of ingested git rationales + past chats, retrieved & surfaced | ❌ | ✅ |

So the comparison is **"no memory system" vs "memory system"**, holding the agent fixed. What that
means per task depends on **where the decision lives**:

## Axis 1 — source (where the decision lives)

- **`history`** (git history) — the decision is a real commit's rationale in the repo's history. The
  plain agent *can* reach it (`git log`/`blame`) but often doesn't think to; memory surfaces it. **The
  fair test: both arms can reach it; memory is about reliability, not access.** (Note: a *strong* agent
  like sonnet-5 reliably mines git history, so `history` tasks are easy for it — they discriminate mainly
  for weaker agents.)
- **`conversation`** — the decision was made in a past developer chat, never written into the repo.
  The plain agent *cannot* reach it at all; only a memory system that captured the chat can. **The
  "memory is necessary" test** — and the better discriminator for strong agents.
- **`conversation-amended`** — the decision was settled in an EARLY chat and **amended in a later
  one**; only the amended rule is correct, and the pre-amendment rule is deliberately one of the
  task's proven naive fixes. Tests **cross-chat consolidation**: a memory system that surfaces the
  stale first decision fails the hidden test exactly like a guesser. Both chats are available to
  both arms (seeded sessions for the plain agent; ingested for memory).

## Axis 2 — tier (how the task is hosted)

Both tiers live **inside the real boltons repo** (real git-history noise + real-repo navigation). They
differ in *what the buggy code is* and *what grades the fix*:

- **real-function** — the policy sits on an *untested edge* of an **existing, real boltons function**
  (e.g. `strutils.slugify`). Boltons' own code doesn't implement the project's policy — that gap **is**
  the bug; the agent edits the real function. Graded against boltons' **real test suite** (must stay
  green) + repro + hidden. Authentic and harder — nothing was fabricated for the agent.
- **planted** — a validated trap as a **new small module written into the boltons repo** (e.g.
  `retryx/retry.py`) with a buggy implementation at HEAD; the agent fixes that module. Graded against
  the module's **own tests** + repro + hidden. Controlled — you author the code and tests.

See `GENERATING.md` for how tasks are built and how to add one.

## Axis 3 — category (the kind of decision)

Orthogonal to source and tier: **what kind of non-guessable rule** the fix hinges on. The canonical
taxonomy is `gen/categories.py`; `MANIFEST.json` groups by it (`by_category`). Reporting interventions
per category shows *where* memory helps most.

- **mapping** (slugify, pluralize) · **set-membership** (under2camel, parseflag) · **numeric-policy**
  (rounding, budget) · **ordering** (discount) · **collection-merge** (listmerge) · **filter-rule**
  (findhashtags) · **invariant** (omdset)

## Host & noise

[boltons](https://github.com/mahmoud/boltons) (BSD, ~1600 commits, pinned at `979fa9b`) is the host,
used as a fixture (cloned, not vendored). Its **~1500 real commit subjects + rationale bodies** seed
the memory store as retrieval noise, plus decoy chats — so surfacing the right decision is a real
ranking problem, not a lookup.

## Tasks (19)

| task | source | tier | category | module/fn | non-guessable policy |
|---|---|---|---|---|---|
| budget | conversation | planted | numeric-policy | `retryx/retry.py` | exactly 7 (measured to the rate-limit window) |
| discount | conversation | planted | ordering | `billing/discount.py` | percent discounts apply before fixed-amount |
| findhashtags | conversation | real-function | filter-rule | `boltons/strutils.py` | drop all-numeric tags EXCEPT 4-digit years (1900-2099) |
| listmerge | conversation | planted | collection-merge | `confmerge/merge.py` | union list values (de-duplicated, base order first) |
| parseflag | conversation | planted | set-membership | `cfg/flags.py` | truthy set is exactly {'true','on'} |
| pluralize | conversation | real-function | mapping | `boltons/strutils.py` | formal/DB plurals person->persons, index->indexes, matrix->matrixes |
| rounding | conversation | planted | numeric-policy | `pay/rounding.py` | round half-cents DOWN (ROUND_HALF_DOWN) |
| slugify | conversation | real-function | mapping | `boltons/strutils.py` | SEO symbol map & to and, $ to usd, % to pct |
| under2camel | conversation | real-function | set-membership | `boltons/strutils.py` | acronym set {HTTP,API,SKU,GDPR} uppercase; db/sql/url stay title-cased |
| budget-history | history | planted | numeric-policy | `retryx/retry.py` | exactly 7 (measured to the rate-limit window) |
| discount-history | history | planted | ordering | `billing/discount.py` | percent discounts apply before fixed-amount |
| findhashtags-history | history | real-function | filter-rule | `boltons/strutils.py` | drop all-numeric tags EXCEPT 4-digit years (1900-2099) |
| listmerge-history | history | planted | collection-merge | `confmerge/merge.py` | union list values (de-duplicated, base order first) |
| omdset | history | real-function | invariant | `boltons/dictutils.py` | __setitem__ must reset the underlying value list to [v] after _remove_all (not reuse add() |
| parseflag-history | history | planted | set-membership | `cfg/flags.py` | truthy set is exactly {'true','on'} |
| pluralize-history | history | real-function | mapping | `boltons/strutils.py` | formal/DB plurals person->persons, index->indexes, matrix->matrixes |
| rounding-history | history | planted | numeric-policy | `pay/rounding.py` | round half-cents DOWN (ROUND_HALF_DOWN) |
| slugify-history | history | real-function | mapping | `boltons/strutils.py` | SEO symbol map & to and, $ to usd, % to pct |
| under2camel-history | history | real-function | set-membership | `boltons/strutils.py` | acronym set {HTTP,API,SKU,GDPR} uppercase; db/sql/url stay title-cased |

Per-task metadata is in each `task.json` (`source`, `tier`, `category`, `module`, `function`,
`policy`, `non_guessable`); summary + `by_source`/`by_tier`/`by_category` counts in `MANIFEST.json`.

## Grading & metric

Grading (Docker, pristine test copies): `pass_to_pass` (existing behaviour) + the repro
(`FAIL_TO_PASS`, red at HEAD) + a **held-out hidden test** (`HIDDEN_TO_PASS`). Every task is verified:
`HEAD` fails repro+hidden, the correct fix passes all, the *naive* fix passes repro but **fails hidden**
(non-guessable). Empirically confirmed too: the plain agent needs interventions on every task.

Primary metric: **interventions** — on a failing grade the harness feeds back the failing-test output
and resumes (cap 5). 0 = solved first try, no human help. Also: turns, cost, solve rate.

## Memory & results

The dataset is **memory-system-agnostic**: any system that ingests the project's knowledge (git
rationale commits + past developer chats) and surfaces the relevant decision to the agent can be
plugged in. A well-behaved system surfaces the *decision*, not the hidden-test values (no answer
leakage) — the agent still writes and tests the fix.

Empirically the dataset discriminates: the plain agent needs interventions on essentially every task,
and a memory system that surfaces the right decision drives interventions toward zero. Reproduction and
per-arm results live in the runner,
[open-memory-benchmark](https://github.com/vectorize-io/open-memory-benchmark).

## Validate & run

This repo is the **dataset**. To validate structural integrity:

```
python validate.py            # 10 boltons-* tasks: fields, tests parse, manifest consistency
```

To actually run the benchmark (build each task's repo, drive an agent, grade in Docker, count
interventions), use the runner in
[open-memory-benchmark](https://github.com/vectorize-io/open-memory-benchmark), which mounts this repo
as a submodule at `sdebench/datasets` and runs e.g.
`uv run omb run --dataset sdebench --split boltons --mode coding --memory {none|hindsight-http}`.

boltons is © Mahmoud Hashemi, BSD — used unmodified as a fixture. Traps, planted modules, tests,
chats, and this datasheet are this project's.
