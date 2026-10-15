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
3. **Implement.** Edit a coherent change directly within the project's enforced
   budget; project risk paths and write allowlists win. File count alone does not
   require another worker. Use a native Codex role or `scripts/worker.py` when
   delegation is authorized and an independent unit improves throughput. Codex workers return evidence; the lead retains
   ownership. Do not dispatch the original Claude-first `codex-task.sh` here. For
   a bare-metal binding, work directly in the existing bound development checkout
   and branch. If an older worktree holds the reviewed change, apply it there
   while preserving existing work; do not create another worktree or merge changes
   into main.
4. **Validate.** Review the completed deliverable and use its affected checks.
   Reuse workers' successful logs for unchanged code; the lead does not repeat
   the same suite for ownership. Finish all writers before the final batch.
   Serialize checks sharing database names, fixture state or a native build target;
   parallelize only independent resources. Fix failures in one batch, verify once.
   Save logs and identify their source revision. Read-only
   investigations need source verification rather than a fabricated diff audit.
5. **Claude audit.** Audit once per coherent deliverable after required checks
   have finished and passed. Do not audit a moving diff, each worker fragment,
   formatting-only follow-ups, or a test run whose result is still pending.
   Include successful check evidence and existing context in the saved plan.
   For that completed change, call the bundle's
   `scripts/handoff.py --root ROOT --plan PLAN --files FILE...`. Include narrowly
   scoped `--context path:start:end` ranges when the diff alone is insufficient.
   Exit 0 means PASS; exit 3 means issues; exit 2 means the audit could not finish.
   The auditor has no tools and receives only the bounded evidence packet.
   An explicit `--previous` PASS is reused without calling Claude only when the
   source, context, plan, base, model and audit contract are identical.
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
update task statuses as work changes, and verify the live session Tasks section.
Use canonical `in_progress` (legacy `running` normalizes to it); progress is not proof of execution.
Four-column task tables remain supported; optional Owner, Activity and Active until columns
report a short agent activity lease. Set owner/activity on assignment/start, renew only during
actual work, and clear `--active-for 0` on worker exit, waiting or shell completion. Active
requires `in_progress`, owner, activity and an unexpired lease; it is not a verified PID.
Do not mark done until required checks and audit are complete. Read
[task tracking](references/task-tracking.md) for the helper, format and completion rules.

## Keep work moving

Choose a coherent deliverable with observable acceptance criteria, not a quota of files or phases. Reuse the current scan, source evidence, plan and loaded skills until an assumption changes. Once the cause and required behavior are established, implement; another investigation needs a named unresolved question.

Default file budgets size briefs; they are not user approval gates. The lead may extend a bounded read-only investigation to directly related source/assets without asking the user. A worker reports the needed paths and continues independent work; the lead answers promptly. Explicit project prohibitions and enforced write allowlists still apply: amend the brief before writing a newly required path.

When delegation is authorized, give independent implementation and validation work to available workers with disjoint write ownership. Do not serialize unrelated units behind a single worker. Resume an idle worker using the runtime's task/follow-up operation; a message that does not start execution is not a dispatch. Track actual activity, and clear activity when work pauses or finishes.

Batch validation and one independent audit around the completed deliverable, including coupled worker changes. Do not audit each exploratory step, asset or file separately. Re-run only checks affected by repairs or new evidence. Preserve required lane gates, audit independence and authorization boundaries.

If progress stalls, inspect actual worker/tool activity and the outstanding dependency, then remove the bottleneck or rebalance the work. Explain concrete completed behavior and the next deliverable; repeated planning or status updates do not count as implementation.

Keep operation boundaries aligned with delivery: perform one native reload after
an integrated batch passes, then verify readiness. Avoid restarting services for
each worker fragment; account for automatic watchers before concurrent edits.
A status question or continuation does not restart intake, planning or completed
checks. Keep the task registration bound to the session cwd even when operating
on a second repository; do not overwrite it with that repository's task ledger.
