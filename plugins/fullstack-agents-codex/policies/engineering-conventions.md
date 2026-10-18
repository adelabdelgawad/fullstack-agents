Reusable engineering conventions, optional; a repository enables this profile with `policy_profile=engineering-conventions` in `.claude/fsa-team.conf`.

## Every agent

- Repro before hypothesis: one red-capable command (test, curl, trace) or say it is a guess.
- Verify in minutes: define the smallest observation that proves the change and read it as soon
  as enough events exist. No soak periods.
- Conventional commits with the `Co-Authored-By` trailer.
- Tests: compiling (`check`) is not testing: batch it once per workspace per task group. Do not
  edit failing tests you did not break; when replacing a builder behind a live list, the old
  path's test is the acceptance gate. For any non-trivial test, name the defect that fails it and
  prove it by removing the production line. `cargo check` validates neither SQL in string literals
  nor DB rows paired with Rust constants. Never hand-write `CREATE TABLE` for a migrated table in
  a test fixture. Build fixtures from real production design rows, not shapes written beside the
  implementation.
- Evidence: before reporting a count or root cause, state what a row means, its null cases and
  the observation that would falsify the cause; name individual items behind a surprising count.
  Measure performance before and after; never report a perf fix from the diff alone. Render and
  look at a visual change before handing it back.
- Before deleting a file as orphaned, check whether its features were re-homed; zero importers
  does not prove no feature. When adding a field to a shared DTO, grep every constructor.
- Code quality: root causes, no suppressions (`eslint-disable`, `@ts-ignore`, `#[allow]`,
  `unwrap()` on fallible paths), no `any`, no orphaned code.
- Comments, in every file type and every edit (own or delegated): one durable invariant in one
  line, or nothing. No multi-line blocks or header essays; never restate the code, explain why a
  design was chosen, what was rejected, what a previous version did or what an audit found. That
  rationale goes in the commit message or `docs/`; the code gets a one-line pointer at most.
- Shared-state changes (transactions, multi-writer tables, NOTIFY, sweeps, leader election): list
  every writer of each touched table, verify the transaction boundary, walk concurrent writer /
  retry replay / crash between writes / recovery sweep.
- Shared patterns: fix the shared source when a symptom comes from one; list sibling surfaces
  touched or skipped.
- Preview servers bind to `0.0.0.0`; share the machine's reachable host or IP, not `0.0.0.0`.

### Verification checklist (once per integration boundary)

- Focused checks for the touched behaviour; workspace-wide only when the change is broad.
- No suppressions, no `any`, no `unwrap()` on fallible paths, no orphans.
- A migration if the data model changed; the API contract and its regenerated client if the
  contract changed; the architecture docs if a boundary or invariant changed.

## Lead

- Work autonomously; decide, state the decision in one line, proceed. Hard stops: destructive or
  irreversible actions only. Interpret new requests by intent; stop superseded work at a safe
  boundary.
- `file:line` belongs in briefs and reports, not chat. Deliver investigations and audits in chat
  by default; apply the repository's documentation policy for files.
- Cross-session handoffs name one owner of the next step, a deadline and a fallback.
- Deliver written files with their full absolute path. Answer in plain language, simple version
  first.
- Never wait on an agent you have not just seen alive (running task, growing log, recent commit).
  Adopt a dead agent's work.

### Monitoring

"Monitor this" always means the same lifecycle. Never watch a deploy by polling from Claude's own
context.

1. **Runner**: a background loop of `codex exec -m <monitor_model> --sandbox read-only` (`monitor_model=` in
   `.claude/fsa-team.conf`), one cycle every ~10 min, bounded cycle count. Read-only always: the
   monitor reports, it never writes, deletes, moves, repairs, or runs cleanup.
2. **Brief**: a task-owned brief file naming the exact commands to run — the DB queries, the
   filesystem checks, the `docker logs --since` greps. Facts only; the brief tells it what to
   collect, never what to conclude.
3. **Baseline**: state the cutoff (deploy time, restart time) in the brief. Only records after it
   count; pre-cutoff rows prove nothing.
4. **Output contract**, one block per cycle appended to a log, `STATUS: OK | ATTENTION | ALARM`
   first, then the measured values, then a one-line `NOTE:` only when a human is needed.
5. **ALARM is reserved** for data loss or a service down — name the exact condition in the brief
   (e.g. a referenced `cache_path` whose file is missing). Everything else is OK or ATTENTION.
6. **Claude reads the log on demand**, never per cycle, and reports what the monitor observed
   rather than re-running the checks.

A monitor observing zero events is not a passing monitor. Say "not yet exercised" and keep it
running.
