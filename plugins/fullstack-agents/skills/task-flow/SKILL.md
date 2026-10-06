---
name: task-flow
description: Operating flow for the fullstack-agent session lead — investigate, plan, implement (direct edit within the file budget, otherwise a delegated implementer), audit, loop. Use before the first source edit of any task, and whenever deciding whether to edit directly, delegate an implementation, or delegate a wide scan.
---

# Agent task flow

Operating flow for a repository where Claude (the lead, pinned to Opus 5.5) orchestrates — it plans and reviews — and a
headless Claude Sonnet implements (the plugin's `scripts/codex-task.sh`, model
`FSA_CLAUDE_MODEL_IMPLEMENT`). Grok through opencode (`grok`) and Codex (`codex`) are the
alternatives. When the user asks for another engine, for one task or for the rest of the session,
put `IMPLEMENTER: grok` (or `codex`) in every brief it covers; the brief line wins over `FSA_IMPLEMENTER`, which only a
user's environment sets, because the lead's shell state does not persist between calls. Every engine reads the same `CLAUDE.md`, `AGENTS.md` and `.claude/rules/`, so both sides work
to one set of project conventions.
Everything above **Project bindings** is project-independent; the bindings come from the project.

## Roles

| Step | Owner | Output |
|---|---|---|
| 1. Investigate | Orchestrator | Lane skill loaded first; for latency, server vs client time measured first. Then root cause with `file:line`, the command/event path, minimal fix shape |
| 2. Plan | Orchestrator (Claude, plan mode first; never delegated to the implementer) | ≤ 40 lines: outcome, files with `file:line`, minimum test set, verification commands, deploy class, risks |
| 3. Implement | Orchestrator (small) or Implementer (rest) | The diff, nothing else |
| 4. Audit | Orchestrator (Claude) | The implementer's git diff reviewed for conformity with the brief and the architecture docs (and accessibility on UI diffs), plus the plan's tests re-run |
| 5. Loop | Orchestrator | Re-brief with raw output; two retries, then hand the failure to the user |

The orchestrator owns every step but the writing of large changes. It never delegates the
conclusion, the plan, or the verification. Test execution goes to the Sonnet `fullstack-agents:test-runner`, which saves full logs;
those logs are the evidence the orchestrator reads — the runner's summary is only an index into them.

## The size threshold

A round trip to the implementer costs a brief, a dispatch, a wait, and an audit. For a small
change that is more work than the change. So size decides the route:

- **Direct edit** — the orchestrator edits source itself when the change is within the file
  budget and touches no risk path. It still runs the tests.
- **Delegated** — anything over the budget, or touching a risk path, goes to the implementer with
  a written brief.

Risk paths never qualify for a direct edit regardless of size: vendored upstream forks,
migrations, and the code owning a worker, lifecycle, recovery, leader election or sweep. Size
handles volume; the carve-outs handle damage. Scope those keywords to the language and tree that
actually holds process ownership, or they will match unrelated UI files and tax the common case.

Re-editing a file the current change already opened is free. Only a new path spends budget.

A path an implementer run is *currently* writing belongs to that run — the orchestrator re-briefs
rather than hand-patching it. That claim expires when the run does; a finished run must not keep
its paths locked, or the budget never applies to exactly the files under active work.

## Briefs

A brief is the contract and the audit scope. It states: goal; the plan reference; every path the
implementer may touch; the one document to read; the known-red baseline; the tests that prove the
fix; a `BUILD:` line (one compile or type-check command the implementer runs once at the end); forbidden moves. Keep it under 30
lines. The tests that prove the fix are listed for the orchestrator's audit, not for the implementer to run.

The orchestrator already located every change site with grep while planning, so the brief hands
those locations over: each site as `file:line` (or a line range) with what changes there — for a
SQL site, the placeholder numbers already taken and the free one to use. The implementer then
reads windows around those lines instead of whole files, which is where most of its tokens go. A
brief that only names files makes the implementer rediscover what the plan already knew.

Two rules make the audit possible. Every touched path must be listed up front, so a path changed
outside the list is scope creep and gets rejected. And the known-red baseline must be stated, so
a pre-existing failure is never mistaken for a regression.

The dispatch script enforces the list. The Claude and Grok engines' edit and write tools accept
only the `ALLOWED_PATHS` entries (the Claude engine exports `FSA_IMPLEMENTER_RUN=<run id>` so a
project edit gate can admit exactly `<runs>/<id>.allow`), and the manifest prints `STATUS=OUT_OF_SCOPE` for any other path that
changed during the run (in a shared tree that can be another session, so confirm the author). A
brief over `FSA_MAX_ALLOWED_PATHS` paths (default 8) is refused. So list every file the change
breaks, including tests of removed code, and name a `PATTERN:` file for any test the implementer
must write, so it never browses for one.

An external implementer does not load this plugin's skills. The dispatch script attaches only the
skills the brief's paths need: `rust-correctness` for Rust source, `rust-sqlx` only for repository
or SQL paths, `rust-testing` only for test files, `rust-axum-api` for routes, `rust-nextjs-contract`
for OpenAPI, `nextjs` for frontend source (tests and generated files do not count),
`fetch-architecture` only for hand-written `lib/api/` files, and `senior-engineer` only when the
brief creates a new source file. A `SKILLS: name, name` line in the brief replaces that choice
exactly. Every attached skill is re-sent on every implementer step, so never attach one the unit
does not need.

## Parallel implementation

A change too large for one brief is split into units whose `ALLOWED_PATHS` do not overlap —
typically by directory or layer — and the units are dispatched concurrently, one implementer run
each. Keep a unit to at most 8 files (the dispatch limit): every implementer step re-sends the whole
conversation, so a run's cost grows faster than its step count, and two short runs cost about half
of one long one. A unit whose build or
tests would race another (a shared compile target, a shared database)
waits instead; the project binding caps how many heavy runs share a host. Each unit is audited on
its own diff before the next depends on it; units only start together when neither needs the
other's output.

## Visible workers (only when the user says "use herdr")

Workers stay headless unless the user explicitly asks to use herdr and `HERDR_ENV=1`. Then each
worker runs in its own herdr pane so the user can watch the whole session. Load herdr's own skill
first with `herdr --skill`.

- **Layout.** The first worker splits the lead's pane `down`; every later worker splits the
  rightmost worker pane `right`, so the lead stays on top with one row of workers under it. Always
  `--no-focus`, with the worker's repository root as `--cwd`.
- **Implementer.** Dispatch with `--herdr` (the plugin's `scripts/codex-task.sh`, or the project's
  wrapper around it); the brief, touched-path snapshot and result file stay exactly as headless.
- **Claude workers.** Launch them as ordinary background subagents, then open a read-only viewer on
  each one's transcript with `scripts/herdr-watch.sh <output_file> <name>`. The worker, its cost and
  its result are identical to a headless run; the pane only renders the transcript for the user and
  never enters the lead's context.
- **Hygiene.** Close each worker's pane after its audit. A worker blocked on an approval dialog is
  shown to the user; never answer it on their behalf.

## Watching a run

A dispatched run is never left unattended. Arm a watchdog at dispatch that reports three
outcomes, not only completion:

- **Stuck start** — no sign of work within 5 minutes. Some engines write their log only when they
  finish, so watch the engine's own session activity (for opencode, its session database) or the
  worktree's changed files, not the log size alone.
- **Stall** — work started, then nothing changed for 5 minutes.
- **Finished** — the result file exists.

On a stuck start or a stall, stop the run by its **engine process** (the child whose working
directory is the worktree), not only the wrapper script: a surviving child can wake later and
overwrite files a re-dispatched run wrote. Re-dispatch once; if it hangs again, report it to the
user instead of retrying silently, and tell any peer session waiting on the result.

## Auditing

The implementer's completion report is not evidence. Read the git diff restricted to the paths the
run reports as touched and review it for conformity: the brief's scope, the project's architecture
documents and language lanes, the wire contract, and — on UI diffs — accessibility (labels, roles,
keyboard reach, focus, contrast). Then have `fullstack-agents:test-runner` (Sonnet) run the plan's test commands, and read the
logs it names yourself — grep the result and failure lines, never trust the table alone. A targeted run that skips a surface the
diff touched is not a green result. The implementer does not run test suites (they are denied to the implementer); it runs only the brief's
`BUILD:` compile or type check, so test output never inflates its context.

On frontend diffs, a new `router.refresh()`, a new stream or polling loop, a debounce on a
non-text control, or a static import of a large on-demand sheet/dialog is a review question, not an
automatic violation: the plan or the brief states why it is needed and the evidence that matches it — request fan-out for a refresh,
stream or poll, the measured input delay for a debounce, the measured chunk cost for an import
(`nextjs/references/data-freshness.md`, `live-updates.md`, `client-performance.md`). Scale the
justification to the impact; a one-line reason covers a low-traffic admin page.

Auditing is reading and testing. A fix the orchestrator spots goes back as a re-brief, never into
the file — otherwise the diff under review no longer matches what was delegated.

## Scanning wide

Delegating a sweep is the most expensive read there is, so narrow it before spending a model on
it. Take the cheapest rung that answers the question:

1. **Grep.** Free, no model, and it turns a thousand files into a handful. Always first.
2. **Ranged reads.** If the hits fit in a dozen or so files, the orchestrator reads them directly
   and keeps the conclusion.
3. **Delegated scan.** Only when the narrowed set is still too wide, or one file is too big —
   `fullstack-agents:bounded-extractor` (Haiku) by default. Grok's read-only
   `investigate` mode is opt-in (`FSA_IMPLEMENTER=grok FSA_GROK_INVESTIGATE=1`) for sweeps that need its larger context;
   reading is cheap on Haiku and expensive on the implementer.

A delegated scan gets a narrowed file list and an extraction contract: the exact fields to
report and the shape to report them in. Ask for a table of `file:line` plus values, never prose,
and never "find out why". Prose blows the result cap and smuggles in a conclusion nobody checked;
a table is small and inert.

The orchestrator reads the table and decides what it means. That step is never delegated.

## Cost discipline

Read files with ranged reads, never whole-file shell dumps. Filter command output to what proves
the point: failures, not the passing noise. Pass the failing lines back to the implementer, not
the whole log. Deny agent reads of dependency, build and archive directories.

Batch test execution at the integration boundary — one run per workspace, never per edit or per
task. Write the cases as you go; run them once.

## Working alongside other sessions

When other Claude sessions work on the same repository, `team-coordination` governs every shared
action: claim the task on the board at intake, re-claim on a scope change, hold the `deploy` lock
for a deploy, and on finish leave a note with the SHA, image and migrations for the sessions that
build next. Base a release on the commit production runs, not on a default branch that drifted.
A peer waiting on your result is never left waiting on silence: follow `team-coordination`'s
handoff rules (one owner of the next step, a deadline and a fallback on every wait).

## Project bindings

The project supplies these values in its `CLAUDE.md` or in a bindings file that `CLAUDE.md` names.
A binding the project leaves unset means that route is unavailable, not that a default applies.

| Binding | Value |
|---|---|
| Orchestrator | `fullstack-agents:fullstack-agent` as session lead (activated by the plugin) |
| Implementer | *(command that dispatches one implementation unit; the plugin ships `scripts/codex-task.sh`, which runs headless Claude Sonnet by default; an `IMPLEMENTER: grok|codex` brief line or `FSA_IMPLEMENTER` selects Grok through opencode or Codex)* |
| Wide read-only scan | *(default `fullstack-agents:bounded-extractor`; `codex-task.sh investigate` only with `FSA_IMPLEMENTER=grok FSA_GROK_INVESTIGATE=1`; needs a `FILES:` block and a `REPORT:` line)* |
| Bounded extraction | `fullstack-agents:bounded-extractor` — narrowed file list, mechanical only |
| Read guard | *(hook refusing unranged dumps of gated files)* |
| Scan gate | *(hook refusing a brief without `FILES:` and `REPORT:`)* |
| Direct-edit budget | *(number of uncommitted source files)* |
| Gated extensions | *(e.g. `.rs`, `.ts`, `.tsx`)* |
| Risk carve-outs | *(vendored trees, migrations, process-ownership code)* |
| Build / test entry points | *(project scripts)* |
| Tests never to run | *(any test that touches production)* |
| Enforcement | *(hooks, each with its own test)* |
| Override | *(env var, and it needs the user's word)* |
| Source edits | `Write`/`Edit` only — a shell write skips the gate |
