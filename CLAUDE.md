# CLAUDE.md

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues (`gh` CLI) for `walkerbait/network-device-model`; external PRs are also a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Ralph loop

Spec-driven, one-task-per-iteration agent runner over Kiro specs (`ralph-loop-kiro-specs-script.sh` + prompt). See `docs/agents/ralph-loop.md`.
