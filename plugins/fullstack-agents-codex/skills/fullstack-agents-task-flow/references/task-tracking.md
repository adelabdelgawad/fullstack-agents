# Session task tracking

For a multi-step implementation, maintain a dedicated Markdown task file in the repository the work changes (normally `docs/tasks/<task>.md`), even when the session runs from another checkout: plugin work started from a project directory is tracked in the plugin repository, and project work in the project. Pass that repository's root as `--root`; a root other than the session's cwd must be a git repository root. Keep its scope, acceptance criteria and evidence there. Register it to the actual lead session and original session working directory. A phase journal reports workflow activity; it does not replace the task list.

Use the bundled helper to initialize, bind or update the file. Codex runs `python3 scripts/tasks.py`; Codex runs `scripts/fsa-task` from its plugin. The examples below show the Codex form:

```bash
python3 scripts/tasks.py init --root /absolute/project --file docs/tasks/example.md --title "Example implementation" --task 'T01|in_progress|Inspect existing behavior|Trace the failing case' --task 'T02|pending|Implement and verify|'
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status in_progress --owner lead --activity 'Tracing the failing case' --active-for 120
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status in_progress --active-for 0 --activity 'Waiting for the worker result'
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status done --active-for 0 --note 'Reproduced; required checks passed; evidence saved in the task file'
python3 scripts/tasks.py bind --root /absolute/project --file docs/tasks/example.md
```

Codex phase reporting can bind the file with `scripts/phase.py --root /absolute/project --phase plan --tasks docs/tasks/example.md`. Once registered, every phase reads its current counts, and `complete` is refused while any task is pending, in_progress or blocked, or the registered file is invalid. No task is automatically marked done by a phase change.

The helper defaults to `CODEX_THREAD_ID` or `CLAUDE_SESSION_ID`; pass `--session` when the lead ID is known and not exported. Do not invent a session ID. The registration lives outside the repository; the Markdown file stays versioned with the project. `FSA_TASKS_DIR` overrides the shared registry directory for tools and dashboard together.

The task table is bounded by `<!-- fsa:tasks:start -->` and `<!-- fsa:tasks:end -->`. `init` creates the **v2** format
(below); `init --format legacy` and existing files use the **legacy** format. Existing four-column tables remain supported:

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

Preserve stable IDs. IDs are unique: `add` with an ID that already exists, or twice in one call, fails and leaves the
file unchanged; change a title with `set --title` and everything else with `set`. Use `pending`, `in_progress`, `blocked`,
`done`, `skipped` or `canceled` (v2 adds `verifying`). Legacy `running` is accepted and normalized to `in_progress`; it does not mean a process is running. Only `done` counts as completed. Keep evidence and the next action in the note; name an actual blocking dependency for `blocked`, using its task ID when available. Do not mark implementation done while its required validation or audit remains outstanding.

Task progress and active execution are separate. `in_progress` means unfinished work has started; it may be waiting. A task is active only when its status is `in_progress`, both Owner and Activity are set, and its Active until lease has not expired. Four-column rows have no active lease. `load_tasks` exposes each item's `is_active` and a top-level `active` count. Neither status nor a lease verifies a PID: activity is agent-reported and expires automatically.

Use `set --owner NAME --activity DESCRIPTION --active-for SECONDS` to report current work. `--active-for 0` clears the lease; positive leases are limited to 1–300 seconds. Let the helper write Active until. On assignment, record the responsible owner and activity; leave queued work inactive until it starts. At start, set a short lease with the actual activity. Renew only while that work is occurring, updating Activity when it changes. Clear the lease with `--active-for 0` when a worker exits, work enters a waiting state, or a shell command completes. Record the waiting dependency or next action rather than renewing an idle lease. If verified work continues, start a new lease for that activity; do not infer activity from an unfinished status or mark a task done merely because its worker or command exited.

Update the file when work starts, finishes, blocks or changes scope, including after worker results are verified. The dashboard rereads the file and displays a dedicated Tasks section with counts, per-task status and a link to the Markdown. It shows an error for an invalid or missing registered file; it never turns unreadable work into completion. Do not duplicate a manually maintained task list in phase summaries.

After wiring a task file or changing dashboard support, verify the live session shows it and invite the user to check the dashboard UI. Do not claim a dashboard update based only on a file write.

The dashboard renders task status as an icon with an accessible name and hover label. Owner/activity text stays visible; progress and expiring execution counts remain separate.

## Format v2

v2 adds a Parent column and a task log:

```markdown
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S4 | in_progress | Restart bot after resolution | repair r1: outbox counter | lead | | | |
| S4.v | pending | Journey tests | | | | | S4 |
```

- **Deliverable**: a row with an empty Parent, an independently verifiable result. **Step**: a row whose Parent names a
  deliverable. Parent is set once with `add --parent <ID>`; it must be an existing deliverable of the same ledger (one level,
  no self-parenting). The dot in `S4.v` is a naming habit only; the Parent cell alone decides.
- `verifying`: the work is written and its checks or audit are under way. The dispatcher moves a successful run's row there.
- Progress counts deliverables and steps separately; `skipped` and `canceled` deliverables leave the total. Steps never
  change the deliverable count.
- No step may be open while its deliverable is `done`, `skipped` or `canceled`: a deliverable cannot close over open
  steps, and a step cannot be added or reopened under a closed deliverable; reopen the deliverable first
  (`set --status in_progress --reason …`). Nothing reopens it implicitly. Every v2 write checks this, so a hand-edited
  file that breaks it refuses further writes until it is fixed. Reopening a `done` row needs `set --reason`.
- `## Task log` (between `<!-- fsa:log:start -->` and `<!-- fsa:log:end -->`) receives one line per add, status change,
  title change, upgrade and downgrade. Notes, owners and leases are not logged. The tool never rewrites a log line, and
  refuses a write that would push the file past its size limit.
- A v2 deliverable reaches `done` only through recorded completion evidence (next section). Steps are not gated.
- The header is the format: it must match the 4-, 7- or 8-column header exactly, and a v2 file needs its log markers.
  Anything else is an error, never a fallback to legacy.

## Completion evidence (v2)

Each deliverable declares, before it can close, what "done" means and how it is checked. `fsa-task accept --id S4
--input spec.json` records the spec in a tool-written evidence block of the ledger:

```json
{"kind": "code",
 "scope": {"paths": ["src/backend/crates/x/"],
           "dependencies": ["src/backend/crates/shared/", "src/backend/Cargo.toml", "src/backend/Cargo.lock", "tests/helpers/"],
           "inputs": ["src/backend/.env.example"], "env": ["SQLX_OFFLINE"],
           "rationale": "x and the shared crate it calls; the journeys test reads the helpers and env example"},
 "criteria": [{"id": "AC1", "text": "Journey B restarts the bot", "checks": ["C1", "R1"]}],
 "checks": {"C1": {"method": "command", "command": "scripts/test-backend.sh -p x --test journeys", "cwd": ".",
                   "expect": {"patterns": ["test result: ok\\. [1-9][0-9]* passed"], "reject": ["0 passed"]}},
            "R1": {"method": "review", "what": "diff read against the brief's ACCEPTANCE"}}}
```

- **Kinds and methods.** `kind` is `code`, `docs`, `design`, `investigation` or `other`. Methods: `command` (exit code,
  run log and `expect`), `review` (saved review notes or diff), `inspection` (screenshot, probe output), `document` (the
  document itself), `analysis` (the report with its sources). `code` needs at least one `command` check unless the spec
  carries `automated_waiver` with a reason; other kinds never need one but may use one (a doc checker, a link check).
- **Scope is a declaration.** `paths`, `dependencies` and `inputs` are what the evidence is about: shared modules, test
  helpers, manifests, lockfiles and configuration belong in it. A package boundary is not automatically enough;
  `rationale` says why the scope covers what the checks exercise, and `code` needs dependencies or `dependencies_none`
  with a reason. Edits outside the scope do not affect the evidence, by this policy.
- **`expect`.** Exit 0 alone proves nothing: a `command` check lists regexes its log must match (and may list `reject`
  ones), or `{"none": "<reason>"}` for silent commands. When a command can pass while skipping its work, pair it with a
  `review` check.

**Recording results.** `fsa-task check run --id S4 --check C1` runs the recorded command itself and records `pass`,
`fail` (nonzero exit), `timeout` (the command's whole process group is killed), `unavailable` (missing executable) or
`inconclusive` (exit 0, expectations unmet). An external finish reports only `pass`, `fail`, `timeout` or `unavailable`
(with `--reason`). For a
check run elsewhere (test-runner, a browser, a review), call `check start` first and `check finish --run <id> --result …
--evidence <file>` after; that result is labelled *attested*: fsa-task did not execute it. A finish without its start, a
second finish, or a finish after the check's definition changed is refused. Evidence of `command`, `review` and
`inspection` checks lives outside the scope (the default log directory is outside the repository); the ledger file never
counts as scope. `document`/`analysis` evidence is the subject file inside the scope.

**The gate.** `set --status done` (and `add`/`init` with a done deliverable) is refused unless no step is open, the spec
is valid, and every check used by a criterion has a latest result that is `pass` (or an attributed baseline failure),
was recorded under the check's current definition, saw no scoped change between start and finish, still has its evidence
files unchanged, and matches the scope's current content. `fsa-task verify --id S4` prints the same report without
writing. A later non-pass result on a `done` deliverable reopens it, with the reason logged, in the same row.

**Changing the spec.** Any change to criteria, checks, scope or waivers after a result exists needs `--reason`; it
invalidates exactly the results whose check definition changed, and the log names them. Never edit a spec to get a
deliverable through the gate without saying so to the user.

**Baselines.** `fsa-task baseline --id B1 --command … --ref <commit> --log <file> --signature "<failing test>" --reason …`
records a failure that predates the work: the ref must be an ancestor of HEAD and the log must contain every signature;
the tool keeps the log's hash and a hash of the whole tree at the ref. `check attribute --id S4 --check C1 --baseline B1 --reason …` accepts a later `fail` of the same command only when its log
contains the same signatures. The original failure, both logs, the baseline code state and the reason are kept; the
deliverable shows as *done with baseline failures*, never as a plain pass. `timeout`, `unavailable` and `inconclusive`
results cannot be attributed.

**Freshness and its limits.** A result's code state is a content hash of the scoped files (tracked, untracked and deleted),
the declared inputs and hashed values of the declared environment variables; each check's command, working directory and
criteria are bound separately by its definition digest, so changing one check does not stale the others. It is
computed only when the check starts and finishes, never re-stamped. Committing unchanged content keeps evidence current;
another session's edit to a scoped file makes it stale. It cannot see a change made and undone during a run, anything
outside the declared scope (build caches, toolchains, databases, services, undeclared environment), or a change in the
moment after the gate passes. The evidence identifies what was tested; it does not guarantee the result still holds.

**Completion kinds.** `show` and the dashboard distinguish `done` with evidence, with baseline failures, and *unrecorded*
(closed without passing the gate: before L2, or carried over by `upgrade`). The kind is stamped only when the gate passes
and cleared on every reopen. A malformed evidence block never prevents a reasoned reopen (`set --status in_progress
--reason …`): the block is left byte-for-byte for diagnosis and the log records `evidence_malformed`; completion and every
evidence command stay refused until the block is repaired. `show` and other status changes keep working. Legacy ledgers have no evidence and no gate.

**Compatibility.** Legacy files keep their behaviour; the only changes are duplicate-ID refusal and recovery no longer
listing `skipped`/`canceled` rows as open. `fsa-task upgrade` converts a legacy file to v2 (every row a deliverable; nothing
is inferred from IDs). Releases before v2 reject the v2 header: their dashboard shows an error and their Codex `phase.py`
refuses `complete`, so old tools never report v2 work as finished.

**Rollback.** Before reinstalling an older release, run `fsa-task downgrade`. It refuses while any row is `verifying` or has
a Parent (finish, cancel or record those first), and while an evidence block exists, because a legacy ledger cannot keep
the completion gate; otherwise it restores the legacy table, keeps the task log and appends a
`downgrade` event.

**Outside enforcement.** Every rule above applies only through `fsa-task`, `tasks.py` and the dispatcher. Editing the
Markdown directly (Edit/Write tools, an editor, git) bypasses them; a resulting malformed v2 file is reported as an error.

## Granularity and update cadence

One row per deliverable: the result that is audited and accepted as a whole. Repairs, retries and verification runs
belong to the deliverable they serve: record them in its note (`repair r1: …; tests 9/9 v2b.log`) and keep it open until
its checks and audit pass. A failed check or audit sends the same row back to `in_progress`; it never creates a "follow-up"
row. In v2, a step row (`--parent`) is optional, for a separate brief or check worth showing on its own. A new row is right
only for an independently verifiable result or a real prerequisite; unrelated findings go to the user at hand-back, not
into this ledger. Never one row per phase.

A brief carries `TASK: <ledger.md>#<ROW-ID>` (path relative to the repository root, or absolute). At dispatch the
dispatcher marks the row `in_progress` with the engine as owner and a lease. At finish it hands the row to `lead` with the
note `succeeded: awaiting lead audit (run <id>)` (v2: status `verifying`), or marks it `blocked` with `<state>: see run <id>`.
On a legacy ledger it adds a missing row; on v2 it never adds a row and never touches a `done` row (it warns: add or reopen
the row first). A ledger failure only warns; it never changes the dispatch. The lead marks a row `done` only after its audit
and checks pass, citing the evidence in the note. Update at every event: dispatch, return, check pass or fail, blocker.

Add several rows in one write, apply one change to several rows (an omitted `--status` keeps each row's status), and
report status from the compact summary (`--json` for machine output); Codex passes the same arguments to
`python3 scripts/tasks.py`:

```bash
scripts/fsa-task add --root /absolute/project --file docs/tasks/example.md --task 'S4|pending|Restart bot after resolution|' --task 'S5|pending|Saved selections|'
scripts/fsa-task add --root /absolute/project --file docs/tasks/example.md --parent S4 --task 'S4.v|pending|Journey tests|'
scripts/fsa-task set --root /absolute/project --file docs/tasks/example.md --id S4 --status in_progress --reason 'journey B fails after done'
scripts/fsa-task show --root /absolute/project --file docs/tasks/example.md
```

## Ownership

`init` and `bind` make the calling session the ledger's **owner**. After that, `set`, `add`, `checkpoint` and `close` from any other session are refused, and so is the dispatcher's row update when it runs under another session.

The guard covers only these commands. Direct edits to the Markdown file (Edit/Write tools, editors, git) bypass it: the ledger stays an ordinary repository file. The guard keeps cooperating sessions from writing over each other's tasks; it is not access control.

An owner is reported as one of four states:

| State | Meaning |
|---|---|
| `free` | released |
| `live` | its Codex process, identified by process id **and** start time, still runs |
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
- `HANDOFF:` appears (from `fsa-usage` or the `context-handoff` hook);
- before a manual `/compact` or `/clear`.

Reading files, grepping and worker progress are not triggers. An unchanged checkpoint is not rewritten.

**What a checkpoint is:** a lead-written historical record that can be wrong. Cite a user quote or an evidence path for every decision and result.

- An approval in a checkpoint is a record of what the user said. It never creates or widens authorization; schema validity does not make it one either.
- A clear, restart, resume or compaction does not revoke an approval the user actually gave. Reconfirm only when the scope changed, a limit the user stated has expired, a single-use approval was already used, or the recorded words do not establish it (`ambiguous`).
- Database resets, migrations, service reloads, deploys and releases keep the project's explicit-approval rule: the user's words must name that action for this task; a backup, a checkpoint or an earlier general approval does not.

## Blockers, waiting and continuity (v2)

A row waits only through a typed blocker, and the session's state is derived from rows and blockers, never from reply
wording:

| Command | Use |
|---|---|
| `fsa-task block --rows S3,S4 --kind user --text "<exact question>" --why "<what it blocks>"` | a decision only the user can make |
| `fsa-task block --rows S2 --kind external --class capacity --engine codex --until <reset> [--offer "<alternative needing approval>"]` | an implementer's quota is exhausted |
| `fsa-task block --rows S5 --kind worker --text <run id>` / `--kind external --class infrastructure --text "<condition>"` / `--kind row --text <row>` | a running worker, unavailable infrastructure, a prerequisite row |
| `fsa-task resolve --id B1 --quote "<user's words>"` / `--evidence <file>` | `user`: the quote (at least three words) must occur in one prompt this session recorded (only salted word-hashes of the last 30 prompts are kept, never the text); `worker`: the run's `result.json`; `external`: an evidence file and `--reason`; `capacity`: refused while the engine's window still reads ≥ 100 %; a `row` blocker clears when its row is done |
| `fsa-task withdraw --id B1 --reason …` | the blocker was wrong |

- Session state: `executable` (some open row is unblocked and not held by a live worker) → keep working; otherwise
  `waiting_worker`, `waiting_user`, `waiting_external`, or `done`. Independent authorized work always comes first; a
  pending question never stops it.
- The stop guard holds the turn only while work is executable. In `waiting_user` the final message must state each open
  question (its id or text) and why it blocks; other waits end the turn without forced wording.
- An implementer's exhausted quota is a capacity blocker, not a question. An engine switch is an `--offer`: waiting for
  capacity stays valid, and switching needs the user's authorization. Time passing proves nothing; resolve only after
  `fsa-usage` shows capacity. When usage is unknown (no fresh data, or the Codex edition, which does not ship the usage
  reader) the blocker stays open unless `--evidence <file> --reason` records a manual observation of available capacity.
- A matched `--quote` only proves the words were typed in this session. Resolving with it records the lead's
  interpretation that they answer the question; it authorizes nothing else, and approvals still follow the rules above.
- When the stop guard lets a turn end without progress (Codex Code's repeated-continuation signal, or the guard's own
  cap), it shows the user "released without progress" with the open rows; nothing is marked complete.
- `block`, `resolve` and `withdraw` refresh an existing checkpoint's blockers (and next action) in the same write; the
  deliverable stays open with its failing checks.
- `team-board phase complete` is refused while the ledger has open work; a push declares `review`, never `complete`.

**Continuing.** In the same session nothing is needed: the next prompt receives a one-line status (state, blockers,
failing checks, next action) from the existing binding; never ask the user for a path the binding already holds. After a
`/clear` or restart, session start lists up to three resumable ledgers of this checkout (open work, valid ledger, active
or no checkpoint, owner free or stale; newest first, with a count of any more and the command to list them all). Nothing
binds automatically. When the user asks to continue a task and exactly one candidate matches, bind it with the command
the list shows (`--takeover` only for a stale owner, on that instruction); when several match, ask which. A generic new
request starts fresh. Do not recommend `/clear` or a new session for context size or cost; write the checkpoint instead.

## After compaction, `/clear`, resume or a fork

| Event | What happens |
|---|---|
| Compaction | Same session. A recovery summary of at most 2,500 characters arrives automatically. Ownership is unchanged. |
| `/clear` | Starts a new session. The old session releases ownership. The new session sees at most a short **offer**, never a binding. Continue the old task only when the user asks, with `scripts/fsa-task adopt --root … --file … --from <old-session>`. Otherwise start fresh. |
| Fork (`/branch`) | Same as `/clear`. The copied conversation is not a user instruction to continue, and the fork owns nothing until an explicit `adopt`. |
| Resume | Ownership is re-acquired only when it is free, stale, or held by this same process. Another session's ownership is never displaced: the hook names that owner instead. |

The offer is decided at the first session start in the same Codex process after the clear or branch, and that start consumes it whatever happens. It is shown only once, only for the same checkout and Codex process, and only for a ledger that still has open rows and an active checkpoint. As a safety bound, it is never shown more than 300 seconds after the old session ended. Otherwise nothing is shown.

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
