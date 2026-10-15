---
name: task-flow
description: Operating flow for the fullstack-agent session lead — investigate, plan, implement (direct edit within the file budget, otherwise a delegated implementer), audit, loop. Use before the first source edit of any task, and whenever deciding whether to edit directly, delegate an implementation, or delegate a wide scan.
---

# Agent task flow

Claude remains the lead; headless Claude Sonnet remains the default implementer.
Grok/Codex are alternatives selected by existing bindings or the user's request.
`IMPLEMENTER:` in a brief wins over `FSA_IMPLEMENTER`. Lead planning, audit and
conclusion never transfer to the implementer. Tests run through
`fullstack-agents:test-runner`; the lead reads its saved logs. The project's
`CLAUDE.md` supplies bindings and wins over defaults.

## Always-loaded contract

1. Investigate: load lane skills; search then bounded reads. Measure server vs
   browser time for latency. Establish causes from source/reproduction.
2. Plan first in Claude: at most 40 lines; outcome, files/sites, acceptance,
   minimum tests/commands, deploy class (bare-metal: the services to reload), risks.
3. Implement: direct edits only within the project budget and outside risk paths.
   Re-editing an opened path is free. Live worker paths belong to that run until
   it finishes. Vendored forks, migrations and ownership/lifecycle code always
   go to the implementer; scope these risks to the actual process-owning tree.
4. Audit: read touched-path diff; check scope, architecture, lanes, wire contract
   and UI accessibility. Rerun all affected plan tests via test-runner and read
   logs. Mark every acceptance item with evidence. Worker findings stay
   hypotheses until verified; confirmed repairs go back in bounded briefs.
5. Loop: pass raw failing lines, not entire logs. Two retries maximum, then
   report unresolved issues. Skipped surfaces never count as green.

## Briefs and scans

Briefs are at most 30 lines: goal, `PLAN:`, exact `ALLOWED_PATHS:` (eight by
default), authoritative document, known-red baseline, numbered `ACCEPTANCE:`
with runnable checks, one `BUILD:` command, forbidden moves. Name known sites/
ranges; test changes get a `PATTERN:` example. Attach only needed skills.
Frontend briefs state first-paint data and post-hydration request budget
(zero for primary content). The lead loads `nextjs` before writing the brief.

Search → ranged reads → bounded extraction only if the narrowed set is still
too wide. Delegated scans need exact `FILES:` and `REPORT:` table contracts
(`file:line` plus values); ask for facts, never conclusions. Bounded-extractor
is default; Grok investigation is opt-in. Filter passing noise, deny dependency/
build/archive reads. Batch checks once per workspace/task group, not per edit.

## Conditional detail

Read these detailed guide sections when their condition applies:

- Dispatch: Briefs, Parallel implementation, Watching a run. Split larger work
  into independent, non-overlapping units; honor project host/concurrency limits.
  Five-minute stuck start/stall: inspect actual engine activity, stop the engine
  process before one redispatch, then report another hang.
- Audit: Auditing, including applicable security/UX/code lenses. Reopen findings.
  Frontend changes require the real first-paint trace; lists need list-loading
  rules. Performance complaints load the guide's sweep requirements first.
- Wide reads: Scanning wide. Narrow before spending a model.
- User requests Herdr: Visible workers; otherwise workers stay headless.
- Intake/progress/replies: Reporting the phase; Working alongside other sessions.
  Keep team-board phases/steps current. `team-board wait` precedes a reply needing
  the user. Locks cover only shared operation windows, not builds/peer work.
- Missing/changed project values: Project bindings. An unset binding means the
  route is unavailable; do not invent project defaults.

Reuse sections already in context. Do not reload the whole skill/guide for each
prompt, brief or audit reminder. Detailed rules remain authoritative.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 12: Roles
- Line 26: The size threshold
- Line 47: Briefs
- Line 94: Parallel implementation
- Line 106: Visible workers (only when the user says "use herdr")
- Line 124: Watching a run
- Line 140: Auditing
- Line 184: Scanning wide
- Line 204: Cost discipline
- Line 213: Reporting the phase
- Line 241: Working alongside other sessions
- Line 249: Project bindings

## Task list visible in the dashboard

For multi-step implementation, create and register a dedicated repository Markdown task file,
update task statuses as work changes, and verify the live session Tasks section. Read
[task tracking](references/task-tracking.md) for the helper, format and completion rules.
