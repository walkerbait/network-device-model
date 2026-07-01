# Ralph loop (spec-driven iteration)

A **Ralph loop** drives a spec-aware agent CLI through a Kiro spec one task at a
time until the whole task list is done. Adapted from
[mreferre/ralph-loop-kiro-specs](https://github.com/mreferre/ralph-loop-kiro-specs).

## Files

- `ralph-loop-kiro-specs-script.sh` — the loop runner (repo root).
- `ralph-loop-kiro-specs-prompt.md` — the agent prompt template. Every iteration
  the agent implements exactly **one** top-level task from the spec's `tasks.md`,
  verifies its exit criteria, then records progress and timing.

## How it works

Each iteration the agent:

1. Loads context (`.kiro/steering/*`, the spec's `requirements.md`, `design.md`,
   `tasks.md`, and the `Corrections` + `Codebase Patterns` at the top of
   `progress.md`).
2. Picks the lowest-numbered unchecked top-level task.
3. Implements it and its subtasks, running the tests.
4. Verifies the task's exit criteria against `requirements.md`/`design.md`.
5. Marks the task `[X]` (or `[F]` if blocked), appends a `progress.md` entry, and
   logs elapsed time to `specs_time.md`.

When all tasks are `[X]`, the agent writes `summary.html` and emits
`<promise>COMPLETE</promise>`, which stops the loop.

## Running

```bash
# 10 iterations against the stig-catalog spec
./ralph-loop-kiro-specs-script.sh 10 stig-catalog
```

The script asks whether to run automatically or pause for review between
iterations, prints the prompt for approval, then loops.

The agent CLI defaults to `kiro-cli chat --trust-all-tools --no-interactive`.
Override it for a different non-interactive, spec-aware agent CLI:

```bash
RALPH_AGENT_CMD='claude -p --dangerously-skip-permissions' \
  ./ralph-loop-kiro-specs-script.sh 10 stig-catalog
```

## Available specs

- `.kiro/specs/stig-catalog/` — build the XCCDF → `network_models.stig` importer.
- `.kiro/specs/network-device-model/` — the original device-model spec.

Generated per run (created by the script/agent, safe to delete to restart):
`progress.md`, `specs_time.md`, `summary.html`.
