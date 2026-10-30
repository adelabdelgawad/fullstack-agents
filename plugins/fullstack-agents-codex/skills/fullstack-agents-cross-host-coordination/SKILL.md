---
name: fullstack-agents-cross-host-coordination
description: "Work spanning two hosts that run one repository (an app host and a GPU or ASR host) — delegating to the remote Codex session through herdr, syncing commits both ways, ordered rollout."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

## Engineering guide

The complete adapted rules are in [references/engineering-guide.md](references/engineering-guide.md). Before acting, read its relevant requirements/checklist sections and only the examples you need. Start with the section index below and read at most 200 lines per call. Load the complete guide only when the task spans all of it. Paths inside that guide remain relative to this skill directory, beside `SKILL.md`. Project patterns and the constitution win over template defaults.

- Line 9: Bindings
- Line 16: Ownership
- Line 32: Evidence
- Line 51: State ladder
- Line 57: Workflow
- Line 81: Choosing the integration
- Line 100: Coupled changes and rollout order
- Line 118: Recovery
- Line 130: Record and report
