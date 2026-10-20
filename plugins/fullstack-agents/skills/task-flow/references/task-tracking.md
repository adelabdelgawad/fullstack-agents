# Session task tracking

For a multi-step implementation, maintain a dedicated Markdown task file in the repository the work changes (normally `docs/tasks/<task>.md`), even when the session runs from another checkout: plugin work started from a project directory is tracked in the plugin repository, and project work in the project. Pass that repository's root as `--root`; a root other than the session's cwd must be a git repository root. Keep its scope, acceptance criteria and evidence there. Register it to the actual lead session and original session working directory. A phase journal reports workflow activity; it does not replace the task list.

Use the bundled helper to initialize, bind or update the file. Codex runs `python3 scripts/tasks.py`; Claude runs `scripts/fsa-task` from its plugin. The examples below show the Codex form:

```bash
python3 scripts/tasks.py init --root /absolute/project --file docs/tasks/example.md --title "Example implementation" --task 'T01|in_progress|Inspect existing behavior|Trace the failing case' --task 'T02|pending|Implement and verify|'
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status in_progress --owner lead --activity 'Tracing the failing case' --active-for 120
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status in_progress --active-for 0 --activity 'Waiting for the worker result'
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status done --active-for 0 --note 'Reproduced; required checks passed; evidence saved in the task file'
python3 scripts/tasks.py bind --root /absolute/project --file docs/tasks/example.md
```

Codex phase reporting can bind the file with `scripts/phase.py --root /absolute/project --phase plan --tasks docs/tasks/example.md`. Once registered, every phase reads its current counts, and `complete` is refused while any task is pending, in_progress or blocked, or the registered file is invalid. No task is automatically marked done by a phase change.

The helper defaults to `CODEX_THREAD_ID` or `CLAUDE_SESSION_ID`; pass `--session` when the lead ID is known and not exported. Do not invent a session ID. The registration lives outside the repository; the Markdown file stays versioned with the project. `FSA_TASKS_DIR` overrides the shared registry directory for tools and dashboard together.

The task table is bounded by `<!-- fsa:tasks:start -->` and `<!-- fsa:tasks:end -->`. Existing four-column tables remain supported:

```markdown
| ID | Status | Task | Note |
| --- | --- | --- | --- |
| T01 | in_progress | Inspect existing behavior | Trace the failing case |
```

For owner and current activity, use the optional seven-column format:

```markdown
| ID | Status | Task | Note | Owner | Activity | Active until |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | in_progress | Inspect existing behavior | Evidence in this file | lead | Waiting for worker result | |
| T02 | blocked | Implement and verify | Depends on T01 | worker-api | | |
```

Preserve stable IDs. Use `pending`, `in_progress`, `blocked`, `done`, `skipped` or `canceled`. Legacy `running` is accepted and normalized to `in_progress`; it does not mean a process is running. Only `done` counts as completed. Keep evidence and the next action in the note; name an actual blocking dependency for `blocked`, using its task ID when available. Do not mark implementation done while its required validation or audit remains outstanding.

Task progress and active execution are separate. `in_progress` means unfinished work has started; it may be waiting. A task is active only when its status is `in_progress`, both Owner and Activity are set, and its Active until lease has not expired. Four-column rows have no active lease. `load_tasks` exposes each item's `is_active` and a top-level `active` count. Neither status nor a lease verifies a PID: activity is agent-reported and expires automatically.

Use `set --owner NAME --activity DESCRIPTION --active-for SECONDS` to report current work. `--active-for 0` clears the lease; positive leases are limited to 1–300 seconds. Let the helper write Active until. On assignment, record the responsible owner and activity; leave queued work inactive until it starts. At start, set a short lease with the actual activity. Renew only while that work is occurring, updating Activity when it changes. Clear the lease with `--active-for 0` when a worker exits, work enters a waiting state, or a shell command completes. Record the waiting dependency or next action rather than renewing an idle lease. If verified work continues, start a new lease for that activity; do not infer activity from an unfinished status or mark a task done merely because its worker or command exited.

Update the file when work starts, finishes, blocks or changes scope, including after worker results are verified. The dashboard rereads the file and displays a dedicated Tasks section with counts, per-task status and a link to the Markdown. It shows an error for an invalid or missing registered file; it never turns unreadable work into completion. Do not duplicate a manually maintained task list in phase summaries.

After wiring a task file or changing dashboard support, verify the live session shows it and invite the user to check the dashboard UI. Do not claim a dashboard update based only on a file write.

The dashboard renders task status as an icon with an accessible name and hover label. Owner/activity text stays visible; progress and expiring execution counts remain separate.

## Granularity and update cadence

Track the work at the size it is audited: one row per implementer unit (brief), per repair, and per verification step (compile check, focused tests, lint, visual check, docs), never one row per phase. Rows of one phase share its prefix: `S4a`, `S4b` for units, `V1`, `V2` for checks. A brief carries `TASK: <ledger.md>#<ROW-ID>` (path relative to the repository root, or absolute); the dispatcher then adds the row if it is missing, marks it `in_progress` with the engine as owner and a lease at dispatch, and at finish hands it to `lead` with the note `succeeded: awaiting lead audit (run <id>)`, or marks it `blocked` with `<state>: see run <id>`. A ledger failure only warns; it never changes the dispatch. The lead marks a row `done` only after its audit and checks pass, citing the evidence in the note. Update at every event: dispatch, return, check pass or fail, blocker.

Add or upsert several rows in one write (an existing ID keeps its owner and activity), apply one change to several rows (an omitted `--status` keeps each row's status), and report status from the compact summary (`--json` for machine output); Codex passes the same arguments to `python3 scripts/tasks.py`:

```bash
scripts/fsa-task add --root /absolute/project --file docs/tasks/example.md --task 'S4a|pending|Unit A: API handler|' --task 'V1|pending|Compile check|cargo check --workspace'
scripts/fsa-task set --root /absolute/project --file docs/tasks/example.md --id V1 --id V2 --note 'Waiting for S4a and S4b'
scripts/fsa-task show --root /absolute/project --file docs/tasks/example.md
```

## Ownership

`init` and `bind` make the calling session the ledger's **owner**. After that, `set`, `add`, `checkpoint` and `close` from any other session are refused, and so is the dispatcher's row update when it runs under another session.

The guard covers only these commands. Direct edits to the Markdown file (Edit/Write tools, editors, git) bypass it: the ledger stays an ordinary repository file. The guard keeps cooperating sessions from writing over each other's tasks; it is not access control.

An owner is reported as one of four states:

| State | Meaning |
|---|---|
| `free` | released |
| `live` | its Claude process, identified by process id **and** start time, still runs |
| `stale` | that process is gone, or the process id was reused |
| `unknown` | another host, or the process cannot be checked |

**Taking over another session's ledger:** pass `--takeover <current-owner-session>` to `bind` or `adopt`. Rules:

- Use it **only when the user directs it**. A `stale` or `unknown` state alone never authorizes a takeover.
- The value must name the current owner exactly, so a takeover fails if the owner changed in the meantime.
- The previous owner is kept in the owner record and noted in the ledger's `## Ownership log`.

**Session id:** `--session` defaults to whichever of `CODEX_THREAD_ID` and `CLAUDE_CODE_SESSION_ID` is set. When both are set, `fsa-task` picks the engine that is actually nearer in the process tree. When it cannot tell, it refuses: pass `--session` explicitly. Never copy another session's id.

## Checkpoints

A checkpoint stores the task state that would otherwise exist only in the conversation, in a fenced JSON block inside the ledger. Write it with `scripts/fsa-task checkpoint --root … --file … --input <file.json | ->`.

The input has these fields:

| Field | Content |
|---|---|
| `goal` | the task goal |
| `scope` | `{in, out}` |
| `approvals` | the user's quoted words: `{quote, at, scope, kind: single-use\|task, used, clarity: explicit\|ambiguous}` |
| `decisions` | `{id, text, source}` |
| `constraints` | binding rules |
| `done` | `{text, evidence}` |
| `next` | `{action, owner}` |
| `blockers` | optional |
| `evidence` | paths |
| `verification` | `{command, result: pass\|fail\|other, log, run_at, paths}` |
| `status` | `active`, `completed` or `abandoned` |

Unknown keys are rejected. The tool adds the identity (checkout, branch, HEAD, session, time) and gives each verification entry a fingerprint. That fingerprint records the state when the result was first saved and is never refreshed.

**When to write:** only when the task state actually changes, batching changes made in one turn:

- a user decision or approval;
- a plan approved;
- a batch dispatched, or its result accepted or rejected after audit;
- a verification outcome concluded from its log;
- a blocker appears or clears;
- `fsa-usage` prints `HANDOFF:`;
- before a manual `/compact` or `/clear`.

Reading files, grepping and worker progress are not triggers. An unchanged checkpoint is not rewritten.

**What a checkpoint is:** a lead-written historical record that can be wrong. Cite a user quote or an evidence path for every decision and result.

- An approval in a checkpoint is a record of what the user said, **never an authorization**. Schema validity does not make it one either.
- Ask the user again for anything `ambiguous`, anything outside the quoted scope, and anything the project's rules require a fresh go-ahead for (deploys, migrations, production actions, releases).

## After compaction, `/clear`, resume or a fork

| Event | What happens |
|---|---|
| Compaction | Same session. A recovery summary of at most 2,500 characters arrives automatically. Ownership is unchanged. |
| `/clear` | Starts a new session. The old session releases ownership. The new session sees at most a short **offer**, never a binding. Continue the old task only when the user asks, with `scripts/fsa-task adopt --root … --file … --from <old-session>`. Otherwise start fresh. |
| Fork (`/branch`) | Same as `/clear`. The copied conversation is not a user instruction to continue, and the fork owns nothing until an explicit `adopt`. |
| Resume | Ownership is re-acquired only when it is free, stale, or held by this same process. Another session's ownership is never displaced: the hook names that owner instead. |

The offer is decided at the first session start in the same Claude process after the clear or branch, and that start consumes it whatever happens. It is shown only once, only for the same checkout and Claude process, and only for a ledger that still has open rows and an active checkpoint. As a safety bound, it is never shown more than 300 seconds after the old session ended. Otherwise nothing is shown.

The offer is a convenience, not a requirement. To continue a task later, or after a missed offer:

1. Run `scripts/fsa-task show --root … --file …`. It names the ledger's owner session and state.
2. Only when the user asks, run `adopt --from <that session>`. This works for as long as the old session's binding exists.
3. A `stale` or `unknown` owner still needs the user-directed `--takeover <that session>`.

**Using a recovery summary:**

- It is historical. Re-check the repository before editing.
- A field shortened to fit is marked `[truncated]`, and omitted items are listed under `Omitted:`. In either case the summary says that reading the full checkpoint is required before any edit or dispatch.
- Rerun a check before relying on its result. A verification line marked `inputs changed` or `unknown` certainly needs a rerun.
- Read the full checkpoint before the first edit, and whenever the summary lists omissions.
- `scripts/fsa-task recover --cwd <session cwd>` prints the summary again for the session's bound ledger. `adopt` includes it in its output.

**Finishing:** `scripts/fsa-task close` marks the checkpoint completed and releases ownership. It is refused while rows are open. `release` gives up ownership without closing.

## Codex edition limits

The Codex bundle has no SessionEnd or compaction-recovery hook. In Codex:

- Ownership ends only with `close` or `release`.
- Without a `CLAUDE_PID` ancestor, the owner identity is the **parent process of the `tasks.py` invocation**, usually the shell Codex starts for that one command. That shell exits when the command ends, so a Codex-owned ledger reads `stale` within seconds **while the Codex session may still be active**. In Codex, `stale` does not mean the owner has ended. It still needs the user's direction for `--takeover`, so nothing is lost silently.
- The owning Codex thread keeps writing by its session id.
- After context loss, run `python3 scripts/tasks.py recover --cwd <session cwd>`. To continue another session's task, use `adopt`, as described above.
