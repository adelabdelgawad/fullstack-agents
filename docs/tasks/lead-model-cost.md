# Lead runs on Opus for the whole session (token cost)

<!-- fsa:tasks:start -->
| ID | Status | Task | Note |
| --- | --- | --- | --- |
| T01 | done | Cut execution-phase Opus cost of the lead | 3.83.0: PLAN-HANDOFF at the plan boundary. |
<!-- fsa:tasks:end -->

## Findings (source evidence, 2026-11-07)

- `plugins/fullstack-agents/agents/lead/fullstack-agent.md` frontmatter pins `model: claude-opus-5-5`; the plugin `settings.json` sets `"agent": "fullstack-agents:fullstack-agent"`; `~/.claude-anthropic/settings.json:8` sets `"model": "opus"`.
- Session "transcipt-session-2" (keep-connect, herdr pane w1:p84), three transcript parts under `~/.claude-anthropic/projects/-home-ashadmin-workspace-keep-connect/`:
  - `6cc020a0-…jsonl`: 197 Opus calls, 31.1M tokens, avg context 157k, max 219k; tools Bash 77 (herdr 22, fsa-task 12 with 4 usage errors, polls 6), Edit 10.
  - `8b4c166e-…jsonl`: 146 calls, 20.8M, avg 142k, max 315k.
  - `0289015a-…jsonl`: 174 calls, 29.1M, avg 166k, max 233k.
- Token totals are mostly cache reads (about 0.1x input price); a price-weighted split before and after the plan was fixed is still to do.
- The 200k handoff trigger seldom fires while every call carries about 150k context.

## Levers to evaluate (advisor, unverified)

1. Model switch at the plan boundary: check whether this Claude Code build supports `opusplan` (Opus in plan mode, Sonnet in execution) and whether an agent frontmatter can use it.
2. Handoff at plan approval, not only at 200k; change the lead prompt text ("never advise /clear …") together with the `context-handoff` hook.
3. Execution-phase Bash work (remote herdr driving, fsa-task bookkeeping, polling) to a Sonnet worker or one background script; edit_budget does not see it.

## Next steps

1. Price-weight the 6cc020a0 calls and split them at the first Edit or plan save.
2. Verify `opusplan` support (claude-code-guide agent or docs).
3. Pick the lever, edit the lead prompt, task-flow skill and hook, regenerate the Codex bundle, run `tests/codex` and `tests/dashboard`, bump the version and release (push over SSH to git@github.com:adelabdelgawad/fullstack-agents.git, then `claude plugin marketplace update fullstack-agents` and `claude plugin update fullstack-agents@fullstack-agents`).

## Result (3.83.0)

- Price split (plugin price table, Opus 5.5): 60-66% of each part's cost comes after the first Edit, Write or ExitPlanMode; cache reads are about two thirds of the cost.
- Context at the plan point: 154k, 125k, 173k. A fresh session after a handover starts at 38-75k and is back near 100k after 10 calls.
- What-if over the three parts ($14.46 base): handover at the plan point with 60k fresh context 82%; Sonnet after the plan 89%; both 71%.
- `opusplan` exists but is not a documented agent-frontmatter value, and it runs Opus only inside plan mode, so it does not fit this lead.
- Chosen lever: `context-handoff` gives `PLAN-HANDOFF:` once per cycle on the first edit of a task with a bound ledger at 100k or more (`FSA_PLAN_HANDOFF_TOKENS`, 0 disables); `auto-handoff` arms on it.
- Not done: moving execution-phase Bash chores (herdr driving, polls) to a Sonnet worker; the Opus 5.5 cache-read price (0.05x input in the table) is not verified.
