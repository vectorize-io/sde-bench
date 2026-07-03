# Generating tasks

How sde-bench tasks are built, and how to add a new one. Everything here lives in `gen/` (vendored so
the dataset is self-contained). If you only want to *run* the benchmark, you don't need this file.

## What a task must be

A task is a bug-fix where the **obvious fix is wrong**. Concretely, every task ships two tests:

- a **repro** (`regression_test.py`) — the visible failure the user reports; **red at HEAD**.
- a **hidden test** (`hidden_test.py`) — held out from the agent; encodes the *non-guessable policy*.

A task is only valid if it **discriminates** — i.e. the hidden test can't be bluffed past:

| code state | existing/real tests | repro | hidden |
|---|---|---|---|
| **HEAD** (as shipped) | ✅ pass | ❌ fail | ❌ fail |
| **correct** fix | ✅ pass | ✅ pass | ✅ pass |
| **naive** fix (the obvious guess) | ✅ pass | ✅ **pass** | ❌ **fail** |

The naive column is the whole point: a plausible fix makes the reported bug go away but still violates
the real policy. The policy is *non-guessable* — the only way to get it right is to have the decision
in memory. The generator's validators assert exactly this table for every task before it's accepted.

## The three axes

Each task is tagged on three orthogonal axes (see `DATASET.md` for the full treatment):

- **source** — where the deciding rationale lives:
  - **`history`** — in the repo's **git history** (a real commit's rationale), later dropped by a regression.
    Reachable with `git log`/`blame`. Example: `boltons-omdset`.
  - **`conversation`** — only in a past **developer chat** (`task.json.conversations`), never written to the
    repo. Unreachable without a memory system that captured the chat. (15 of 31 tasks.)
- **tier** — how the trap is hosted (see next section).
- **category** — the *kind* of decision (`gen/categories.py`): mapping, set-membership,
  numeric-policy, ordering, collection-merge, filter-rule, invariant.

## tier: `real-function` vs `planted`

Both tiers live **inside the real boltons repo** (so the agent gets real git-history noise and has to
navigate a real codebase). The difference is *what the buggy code is* and *what grades it*:

### `real-function` — edit a REAL boltons function
The trap is a policy on an **untested edge of an existing, real boltons function** (e.g.
`strutils.pluralize`, `strutils.slugify`). Boltons' actual code doesn't implement *your project's*
policy — **that gap is the bug**. The agent edits the real function, and the fix is graded against
**boltons' own real test suite** (which must stay green) *plus* the repro and hidden tests.

- Authentic and harder: real code, real tests you must not break, nothing was fabricated for you.
- `build.py` = check out boltons@`979fa9b`, trim the test suite to this module's real tests. No code is
  planted — the "bug" is simply that boltons never implemented the policy.
- Defined in `gen/realfn_traps.py`. Emitted by `gen/emit_realfn.py`.

### `planted` — add a NEW module into boltons
The trap is a **new, small module written into the boltons repo** (e.g. `retryx/retry.py`,
`pay/rounding.py`) with a deliberately **buggy implementation at HEAD**. The agent fixes *that* module,
graded against **the module's own tests** + repro + hidden.

- Controlled: you author the code and the tests, so it's easier to make a clean, discriminating trap —
  but it still lives in the real repo (real history, real navigation).
- `build.py` = check out boltons@`979fa9b`, write the package + buggy module + its existing test.
- Defined in `gen/traps.py`. Emitted by `gen/emit_host.py`.

> One-line mnemonic: **real-function = the bug is a real function that lacks your policy; planted = the
> bug is a new module you added.** Real-function is graded by boltons' tests; planted by its own.

## The pipeline: trap → emit → validate

1. **Trap** — a Python dict with everything needed to plant and validate the policy (fields below).
2. **Emit** — an emitter turns a trap into a task directory (`build.py`, `tasks/main/{task.json,
   regression_test.py, hidden_test.py}`).
3. **Validate** — rebuild the task and assert the discrimination table above.

### Trap fields

`real-function` trap (`gen/realfn_traps.py`):

| field | meaning |
|---|---|
| `module` | the real boltons file to edit, e.g. `boltons/strutils.py` |
| `keep_tests` | boltons' real test files that grade this module (the `pass_to_pass`) |
| `anchor` | a unique snippet in the real function — the insertion point |
| `correct` | `anchor` replacement implementing the policy — **validation only, not shipped** |
| `naive` | `anchor` replacement = the obvious wrong guess — **validation only** |
| `repro_test`, `hidden_test`, `bug_report`, `conversation` | shipped in the task |

`planted` trap (`gen/traps.py`):

| field | meaning |
|---|---|
| `name`, `pkg`, `module`, `init`, `import_line` | the new module to plant |
| `bug` / `correct` / `naive` | **full module sources** (HEAD-buggy / right / obvious-wrong) |
| `existing_test` | the module's own test (stays green — the `pass_to_pass`) |
| `repro_test`, `hidden_test`, `bug_report`, `conversation` | shipped in the task |
| `decision_subject`, `decision_rationale`, `marker` | the H-commit text + answer-token (source isolation) |

`correct`/`naive` are **never shipped to the agent** — they exist only so the validators can prove the
task discriminates. The agent writes its own fix.

## Add a `real-function` task

1. Pick a real boltons function with an untested edge where your project needs a specific policy.
2. Add an entry to `gen/realfn_traps.py` with the fields above. `anchor` must be a unique string in the
   current boltons source; `correct` must make boltons' real tests + repro + hidden all pass; `naive`
   must pass the repro but fail hidden.
3. Add the task's `category` in `gen/categories.py`.
4. Emit + validate:
   ```bash
   python gen/emit_realfn.py        # emits every real-function task, then prints the discrimination table
   ```
   Want `HEAD=(True,False,False)  CORRECT=(True,True,True)  NAIVE=(True,True,False)` for your task.
5. `python validate.py` (structural) and commit.

## Add a `planted` task

1. Add a trap dict to `gen/traps.py` (a buggy `bug` module, the `correct` policy, `naive` guesses, and
   the tests) and include it in the `TRAPS = {...}` assembly at the bottom.
2. Add its `category` in `gen/categories.py`, and add its name to the emit loop in `gen/emit_host.py`.
3. Emit + validate:
   ```bash
   python gen/emit_host.py          # emits the planted tasks
   python gen/validate.py           # proves discrimination + source isolation for the trap matrix
   ```
4. `python validate.py` (structural) and commit.

> Note: `gen/emit_host.py` and `gen/emit_realfn.py` **overwrite** the task dirs they emit. They only run
> under `if __name__ == "__main__"`, so importing them is safe, but running them regenerates tasks from
> the traps — re-run them only when you intend to (they are the source of truth going forward).

## Host fixture

Both tiers build on top of a local clone of boltons, pinned at `979fa9b`:

```bash
git clone https://github.com/mahmoud/boltons ~/dev/_sdebench_hosts/boltons
# or point elsewhere:
export SDEBENCH_BOLTONS_HOST=/path/to/boltons
```

Boltons is used unmodified as a fixture (cloned, not vendored) — its ~1600 real commits are the
retrieval noise a memory system must rank against.

## Synthetic standalone tasks (optional, not in the published set)

`gen/core.py` + `gen/emit.py` + `gen/validate.py` are an **older, boltons-free** path: they build a tiny
standalone library repo and plant a trap into its git history (source **`history`**) or only its conversation
(source **`conversation`**), emitting `gen-<trap>-<source>` dirs. The published dataset is entirely boltons-hosted,
so these aren't used, but the code is kept for authoring controlled synthetic tasks with full history.
