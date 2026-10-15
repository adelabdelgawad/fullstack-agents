---
name: fullstack-agents-task-flow
description: Run the Codex-led fullstack change flow with a bounded Claude audit and scoped Codex repairs. Use at intake for investigation, planning, implementation, review and validation.
---

# Codex-led task flow

Codex owns investigation, planning, implementation, validation, repairs and the final result. Opus, through Claude, only audits completed changes as an independent bounded read-only auditor.
Read the bundle's `AGENTS.md` for runtime bindings and token discipline.

1. **Investigate.** Before any branch or worktree decision, resolve the project
   execution binding from project instructions and the configured development
   launcher (for example, a `ucm` symlink) or known existing development checkout.
   Follow the bound checkout's current rules even if the session started from a
   stale default-branch checkout. Check `git status --short` there and preserve
   other work. Search before broad reads. Load only the applicable lane skills;
   scan once for source changes. Establish the actual cause with source evidence
   or reproduction.
2. **Plan.** Keep a saved plan to approximately 40 lines: outcome, exact files,
   acceptance criteria, minimal checks, risks. Resolve only material ambiguity.
   Existing authorization permits continuing; do not add approval round trips.
3. **Implement.** Edit small changes directly, within three source files by
   default; project risk paths and budgets win. For larger changes, use a native
   Codex role when delegation is authorized, or the bundle's `scripts/worker.py`
   for a bounded headless unit. Codex workers return evidence; the lead retains
   ownership. Do not dispatch the original Claude-first `codex-task.sh` here. For
   a bare-metal binding, work directly in the existing bound development checkout
   and branch. If an older worktree holds the reviewed change, apply it there
   while preserving existing work; do not create another worktree or merge changes
   into main.
4. **Validate.** Review the diff and run the affected project's checks from its
   detected roots. Fix failures in one batch, verify once, save logs. Read-only
   investigations need source verification rather than a fabricated diff audit.
5. **Claude audit.** For a completed source change, call the bundle's
   `scripts/handoff.py --root ROOT --plan PLAN --files FILE...`. Include narrowly
   scoped `--context path:start:end` ranges when the diff alone is insufficient.
   Exit 0 means PASS; exit 3 means issues; exit 2 means the audit could not finish.
   The auditor has no tools and receives only the bounded evidence packet.
6. **Repair.** Read `handoff.json` and `repair-brief.md`. Reopen every cited source
   location; reject unsupported findings with evidence. Fix confirmed issues
   only within their repair scope. A new required path must be surfaced before
   broadening the work. Revalidate and rerun the focused audit, including the
   prior handoff as context using `--previous`. Two repair rounds maximum.
7. **Conclude.** State what changed, checks run, audit verdict, and limitations.
   An incomplete Claude audit remains incomplete. Do not claim approval from a
   worker's summary or start a deploy merely because checks passed. Bare-metal
   implementation is complete only after authorized changes are integrated and
   committed to the bound development branch and affected native services are
   reloaded with the project command. Verify the target database and service
   binding first. "Do not deploy" prevents merges into main, production publication,
   and Docker production app image builds or restarts; it still permits an
   authorized native development reload or development migration unless the user
   explicitly forbids reloads, migrations, or commits. Never infer permission to
   mutate production from development authorization.

## Headless Codex worker brief

```text
PLAN: none: the Codex lead owns the saved plan
ALLOWED_PATHS:
- app/example.py

SKILLS: fastapi senior-engineer
PATTERN: app/existing_example.py:20:80
TASK: implement the agreed change
ACCEPTANCE: concrete observable behavior
CHECKS: the exact bounded commands, or lead validates
```

Use exact repository-relative paths, at most eight by default. Workers inherit
the configured Codex model unless explicitly overridden. Investigations are
read-only. Implementation scope is audited after execution; the workspace
sandbox is not a per-file allowlist. Isolate concurrent writers in worktrees
unless project instructions bind development to an existing bare-metal checkout;
that same-checkout binding wins and no additional worktree is created.
Investigative briefs require `FILES:` and `REPORT:`; ask for facts with source
locations, not an unbounded repository sweep. Test-writing briefs name a
`PATTERN:` example so the worker does not browse unrelated test suites.

## Explicit workflow progress

Report every transition with the bundle's CLI:

```bash
python3 scripts/phase.py --root ROOT --phase investigate
```

Keep `ROOT` equal to the original session working directory so dashboard matching
uses the exact startup path. Run project commands from the separately resolved
execution checkout without changing the phase journal root.

Use `plan`, `implement`, `validate`, and `audit` as the work advances; report
`implement` again for repairs, followed by validation and audit. Report
`complete` only after the work is actually complete. The session defaults to
`CODEX_THREAD_ID`; use `--session ID` when it is absent. Atomic journals live in
`$CODEX_HOME/fsa-flow` (default `~/.codex/fsa-flow`); `--state-dir` overrides this
location. The optional shared dashboard reads its default journal location.
Phase writes need no user approval. Their bounded history records progress and
never replaces checks, audit evidence, or authorization for commit/deploy.
The dashboard shows validation/audit as Review and completed Codex work as Done.

## Task list visible in the dashboard

For multi-step implementation, create and register a dedicated repository Markdown task file,
update task statuses as work changes, and verify the live session Tasks section. Read
[task tracking](references/task-tracking.md) for the helper, format and completion rules.
