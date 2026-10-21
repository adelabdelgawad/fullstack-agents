# Task lifecycle: planning, completion and progress semantics

Status: **implemented in 3.67.0**: L1′ (§11), L2 (§12), reduced L3 (§13.10), limited L5 and continuity (§14). Deferred: L4 (discovery commands), §14.4 scheduled wake-up, Jev. Sections are kept in decision order; later sections win where they differ.
Owner: the requesting user. Written 2026-10-20 by a read-only Claude session from the UCM checkout.
Canonical destinations once accepted: `skills/task-flow/references/task-tracking.md`, `skills/task-flow/SKILL.md`,
`skills/task-flow/references/skill-guide.md`, `agents/lead/fullstack-agent.md`, `scripts/lib/task_tracking.py`,
`scripts/lib/stop_guard.py`, `scripts/team-board`, `hooks/auto-phase`, `scripts/fsa-dashboard`, `scripts/lib/dashboard.html`,
and the Codex bundle under `integrations/codex/`. Retire this file when every unit in §9 is accepted, rejected or superseded.

Baseline: plugin `main` at `075e714` (3.66.0). All `file:line` references are relative to
`plugins/fullstack-agents/` unless they start with `integrations/` or `docs/`.

Evidence labels: **[S]** read in source; **[H]** task-history record (ledger file, transcript, classifier log);
**[I]** inference from [S]/[H], not observed directly; **[P]** proposal.

Out of scope, kept separate as requested: Jev integration, reread optimisation, checkpoint/recovery internals.

---

## 1. Checkpoint/recovery status (discovered, not assumed)

- Feature commit `2eb2bf5` and release commit `075e714` (3.66.0) are on `main` and pushed [S: `git log`]. The team board
  records "3.66.0 released + active for NEW sessions" [H]. This session runs 3.66.0 (its plugin script path).
- Its design `docs/TASK_CHECKPOINT_RECOVERY_DESIGN.md` is committed in `2eb2bf5`. Its ledger
  `docs/tasks/task-checkpoint-recovery.md` (all 27 rows `done`, `REL` done) is **untracked** in the main checkout. The ledger is still bound to session
  `b8c9807b` in `~/.local/state/fullstack-agents/tasks/` [H]. This design does not touch that ledger or binding.
- Consequence for this design: ownership, `checkpoint`, `recover`, `adopt`, `close`, the SessionStart/End and PreCompact
  hooks exist and are the base to extend. Nothing below replaces them.

## 2. Current lifecycle, traced

### 2.1 The structures that carry progress today

| Structure | Writer | What it holds | Source |
|---|---|---|---|
| Ledger table (`docs/tasks/<task>.md`) | lead via `fsa-task`; dispatcher via `TASK:` | flat rows: ID, status, title, note, owner, activity, lease | `scripts/lib/task_tracking.py:22,112-131` |
| Checkpoint JSON (in the ledger) | lead via `fsa-task checkpoint` | goal, scope in/out, approvals, decisions, constraints, `done[]`, `next`, blockers, `verification[]`, status | `scripts/lib/task_checkpoint.py:20` |
| Board phase | lead `team-board phase`; `auto-phase` hook | one of investigate/plan/implement/audit/review/complete | `scripts/team-board:17,286-292`; `hooks/auto-phase` |
| Board steps | lead `team-board steps` | 3-8 plain-language steps with state | `scripts/team-board:161-180`; `skill-guide.md:283-291` |
| Board wait | lead `team-board wait`; `reply-classify` (Haiku) | free text "need" | `scripts/team-board:298-305`; `scripts/fsa-classify` |

Four progress structures, written independently, none referring to another. Steps, rows and checkpoint `done[]` can all
describe the same work and disagree [I].

### 2.2 Who creates tasks and changes status

- **Lead** creates rows (`init`, `add`) and sets any status (`set`) [S: `task_tracking.py:504-546`].
- **Dispatcher**: a brief's `TASK: <ledger>#<ID>` adds the row if missing, sets it `in_progress` with the engine as owner,
  and on finish hands it back as `in_progress` "succeeded: awaiting lead audit" or `blocked` [S: `scripts/lib/task-row.sh:45-71`].
  This part is correct: a run's success never sets `done`.
- **Nobody else.** No hook ever sets `done`.

### 2.3 What "done" means today

- Row level: "Only `done` counts as completed … Do not mark implementation done while its required validation or audit remains
  outstanding" (`skills/task-flow/references/task-tracking.md:36`); "The lead marks a row `done` only after its audit and checks
  pass" (`task-tracking.md:50`); "One item not met means the unit is not done" (`skill-guide.md:200-201`).
- Session level: "Done means … tests … green against the stated known-red baseline; the diff was read …"
  (`agents/lead/fullstack-agent.md:144-148`).
- **Enforcement: none.** `set --status done` accepts any row in any state, needs no evidence, and keeps no record of the change
  [S: `task_tracking.py:525-546`]. Acceptance criteria live only in briefs (`ACCEPTANCE:`) and chat; the ledger has no field for
  them and the checkpoint's `verification[]` entries are not linked to any row [S: `task_checkpoint.py:123-131`].

### 2.4 Confirmed defects (source)

| # | Defect | Evidence |
|---|---|---|
| D1 | The granularity rule itself makes repairs and checks separate rows: "one row per implementer unit (brief), per repair, and per verification step". A repair is a new row by instruction, so a failure after "done" cannot reopen the original. | `task-tracking.md:50`; `skills/task-flow/SKILL.md:126` |
| D2 | `done` has no gate: no evidence, no open-child check, no failed-check check, no reason on reopen, no history. | `task_tracking.py:525-546` |
| D3 | `add` with an existing ID silently overwrites status, title and note (upsert), so a resumed session re-adding its plan erases state instead of being refused. | `task_tracking.py:511-517` |
| D4 | Progress = `done rows / all rows`; repairs, checks, audits, parent and child rows all count equally. | `task_tracking.py:225-228`; `scripts/lib/dashboard.html:2139,2163,2166,2198` |
| D5 | Claude's `team-board phase complete` and the `auto-phase` push hook mark the session Done with open ledger rows. The Codex edition refuses the same transition. | `scripts/team-board:286-292`; `hooks/auto-phase:34-51` vs `integrations/codex/scripts/phase.py:118-123` |
| D6 | The dashboard phase is derived from runs, edits and declared phases and never consults the ledger, so "complete" shows while rows are open. | `scripts/fsa-dashboard:2118-2150` |
| D7 | Waiting is computed from the reply text (`?`, an ask regex, or a Haiku classification) and is not linked to any row. `stop_guard` releases on `Waiting on: you - …` even when unblocked `pending`/`in_progress` rows exist. | `scripts/fsa-dashboard:1308-1318`; `scripts/lib/stop_guard.py:93-99,111-113` |
| D8 | The recovery summary lists every non-`done` row as open, including `skipped` and `canceled`; `close` treats those two as closed. | `scripts/lib/task_recovery.py:218` vs `task_tracking.py:391` |
| D9 | A repair brief that reuses a `done` row's ID silently flips it to `in_progress` with no reopen reason. | `task-row.sh:52` |

### 2.5 Instruction ambiguity

- `task-tracking.md:36` (implementation not done before validation) conflicts with `:50` (validation is its own row): with a
  separate `V` row, the implementation row's `done` has no defined meaning, and leads mark it done at audit-of-diff time.
- No definition of deliverable versus step, of baseline-red handling at row level, or of what to do with a discovery.
- `skill-guide.md:274` ("answered with nothing left to do" → `phase complete`) never mentions open rows.
- No session-start planning requirement beyond "plan ≤ 40 lines" in chat (`SKILL.md` contract step 2); the plan is not
  bound to the ledger, so after compaction the plan text is gone and only rows remain.
- Unrelated work is told to go to its own repository's ledger (`task-tracking.md:3`) but there is no backlog home.

### 2.6 Model behaviour seen in history [H]

| Ledger | Pattern | Rows |
|---|---|---|
| `fullstack-agents/docs/tasks/task-checkpoint-recovery.md` | Repairs as new rows after the original was `done`. 27/27 "done" of which 9 are repairs (`U1a-R1`, `U1b-R1`, `R2`–`R8`), 4 verification (`V1`–`V4`), 3 audit (`A1`–`A3`), 2 design; ~9 deliverables. `A1` note: "takeover + release defects repaired" after `U1a` was already `done`. | follows D1 |
| `ucm/tasks/chatbot-standalone.md` | **Done before verification**: `S2` "done — Codex done; awaits V2", `S11` "done — Test file written; awaits V2". Then repair rows `S11r1`, `S5br4`, `S5br5`, `S8ar1`, `S2r1` once V2 failed. **Scope growth**: plugin rows `P01`, `P02`, `D01` and unrelated `A01`, `I01`, `A02`, `V2F` in the same ledger. 47/47 shown. | violates `:36`; follows D1 |
| `ucm/tasks/chatbot-builder-k1.md` | **Parent and children both counted**: `R4` + `R4A`, `R4B`, `R4T`, `R4F`, `R4E`; same for `R5`–`R9`. `R4F` "Revert unintended R4B changes" is a repair row. `R5B2` "withdrawn, premise wrong" marked `done` instead of `canceled`. Plugin rows `D1`, `P1`. | D1, D4, status misuse |
| `ucm/docs/tasks/automation-system.md`, `chatbot-builder-ask.md` | Good practice: repairs kept in the original row's note (`A1` "repair r1 for updated_at", `T02` "lead fixed …"). | shows the target is achievable |

No transcript uses Claude Code's native task tools (`TaskCreate`/`TodoWrite`: 0 calls in the UCM and plugin project
transcripts) [H], so the duplicate "follow-up" tasks are ledger rows, not a second task system.

Waiting: of 659 classified replies, 22 were `approval`, 19 `decision`, 13 `answer` [H: `~/.claude/fullstack-agents/classifier.jsonl`].
How many of the approval waits were re-asks of already-authorised work is not recorded [U]; `stop_guard` already blocks one
form of re-ask (`stop_guard.py:97-98`).

### 2.7 Root cause summary

The written rule (D1) and the absent gate (D2) together produce the observed pattern; the model then follows the rule
literally (new row per repair) or breaks the softer rule (`done` before checks) because nothing refuses it. D4 converts both
into inflated progress. D5–D7 let the session look finished or waiting while work remains. These are mostly instruction and
tool defects, not only model behaviour.

## 3. Concepts, mapped onto existing structures [P]

| Concept | Home | Change |
|---|---|---|
| **Goal** | checkpoint `goal` + `scope.in/out` | none (exists) |
| **Deliverable** — independently verifiable result | a ledger row whose ID has no dot (`S4`, `U1a`, `T02`) | rows are deliverables by default; legacy ledgers keep their meaning |
| **Execution step** — work toward one deliverable (brief, repair, check run) | a child row `S4.a`, `S4.r1`, `S4.v1`, or just a line in the deliverable's note/log | dot-ID = child of the row before the dot; children never count as deliverables |
| **Discovery** — finding awaiting classification | `## Discoveries` list in the ledger, appended by `fsa-task discover` | new section, tool-appended, not a row |
| **Backlog** — unrelated or optional work | `## Backlog` list in the ledger (or the other repository's ledger, `task-tracking.md:3`) | new section, never counted |
| **Pending decision** | a deliverable `blocked` on `user: <decision>` + checkpoint `blockers` | `fsa-task wait` writes both and calls `team-board wait` |
| **Known baseline failures** | checkpoint `baseline[]` (new field: `{check, failure, evidence}`) | one schema field |
| **Required checks** | per-deliverable `Checks:` list recorded by `fsa-task accept` | stored in the log (§6), not a new column |

Why dot-IDs rather than a new column: the table already has two accepted widths (4 and 7 columns); the dispatcher already
auto-adds rows by ID (`task-row.sh:50`); existing IDs contain no dots in any ledger read here (`U1a-R1`, `S5br4`, `R4A`), so
a legacy ledger renders unchanged. Step rows are optional: a lead may keep repairs in the note only, as the good-practice
ledgers do.

## 4. Lifecycle semantics [P]

```
pending ──start──▶ in_progress ──code ready──▶ verifying ──all required checks pass + audit──▶ done
   │                  ▲   │                       │  ▲                                          │
   │                  │   └──▶ blocked ◀──────────┘  │                                          │
   │                  └────── a required check fails ┘                     reopen --reason ◀─────┘
   └──▶ canceled / skipped (terminal, reason required, never counted as done)
```

| Proposed | Existing status | Mapping |
|---|---|---|
| planned | `pending` | unchanged |
| active | `in_progress` | unchanged |
| verifying | **new `verifying`** | today: `in_progress` + note "awaiting lead audit" (`task-row.sh:68`). The dispatcher's finish moves to `verifying` instead. |
| blocked | `blocked` | unchanged; note must name the dependency (row ID, `user: …`, or external) |
| done | `done` | gated (§5) |
| dropped | `canceled` / `skipped` | unchanged, reason required |

`verifying` is the only new status. Compatibility: readers of an older pinned release reject an unknown status
(`task_tracking.py:116`), so a ledger written by the new release shows an error on an old dashboard rather than false
progress. The dashboard is host-level and upgrades with the release; ledgers are single-owner. The Codex `tasks.py`/`phase.py`
ship in the same release. Alternative if this risk is unacceptable: keep `in_progress` and derive "verifying" from a
`verify` log event — weaker, because the status column alone would no longer tell the truth.

## 5. Completion rules (deterministic) [P]

`fsa-task set --status done --id X` is refused unless all hold:

1. `--evidence "<log/command/commit>"` is given (recorded in the note and the log).
2. No child row `X.*` is `pending`, `in_progress`, `verifying` or `blocked`.
3. Every required check declared for X (`fsa-task accept --id X --check <name>`) has a latest recorded result of `pass`,
   or `baseline` where the failure matches a checkpoint `baseline[]` entry for the same check.
4. No required check's latest result is `fail` or `unavailable`.

Recording a result: `fsa-task check --id X --name <check> --result pass|fail|baseline|unavailable --log <path>`.
`fail` on a `done` row reopens it (to `in_progress`, logged with the check as reason). `unavailable` keeps the row open and is
listed in the summary; a lead who accepts the gap must say so to the user and record it with
`fsa-task accept --id X --drop <check> --reason "<why; user quote if approved>"`. Dropping or weakening a check is always a
logged event and shown in `show` — never silent.

Reopen: `set --status in_progress` (or `verifying`) on a `done` row requires `--reason`; the dispatcher refuses to move a
`done` row (warns, run unaffected) — the lead reopens first. History is never rewritten: the done event stays in the log.

Phase completion: `team-board phase complete` and the `auto-phase` push hook refuse (hook: skip with a stderr note) while
the session's bound ledger has open deliverables — parity with `integrations/codex/scripts/phase.py:118-123`.

What the tool cannot check: whether the declared checks are the right ones, and whether a fail is truly baseline. Those
stay lead judgement, made visible by the log.

## 6. Audit trail [P]

A tool-appended `## Task log` section in the ledger, one line per meaningful event, like the existing `## Ownership log`
(`task_tracking.py:353`):

```
- 2026-10-20T16:02Z S4 add (after plan) "Restart bot after resolution"
- 2026-10-20T16:40Z S4 accept +check=runtime-tests +check=clippy
- 2026-10-20T17:05Z S4 in_progress→verifying run=implement-20261020-…
- 2026-10-20T17:30Z S4 check runtime-tests fail log=logs/v2.log
- 2026-10-20T17:30Z S4 verifying→in_progress reason="check runtime-tests fail"
- 2026-10-20T18:10Z S4 check runtime-tests pass log=logs/v2b.log
- 2026-10-20T18:12Z S4 verifying→done evidence="v2b.log 9/9; diff audited"
```

Logged: status changes, add/cancel, accept/drop of checks, check results, plan marker, wait/unblock, discover/classify.
Not logged: lease renewals and activity text (they change every few minutes). Bounded: the log is capped (oldest lines folded
into a count) so a long task cannot exceed the ledger's `MAX_BYTES`.

## 7. Progress, discovery, waiting, planning and recovery [P]

### 7.1 Progress counts

`show` and the dashboard report, separately:

`deliverables 4/6 done (+1 added after plan, 1 canceled) · verifying 1 · blocked 0 · steps 9 · repairs 3 · reopened 1`

- Deliverables = rows without a dot, excluding `canceled`/`skipped` from the denominator but listing them.
- Repairs = child rows with `.r` IDs plus reopen events; neither changes the deliverable count.
- "Added after plan" = rows whose `add` event follows the `plan` marker. The total grows; nothing earlier is rewritten.
- Legacy ledgers (no dots, no log): every row is a deliverable, exactly today's count.

### 7.2 Discovery handling (lead instruction, tool records)

| Discovery | Action | Ledger effect |
|---|---|---|
| Failure caused by the current deliverable | repair inside it | reopen or stay `in_progress`; optional `X.rN` child |
| Missing step required by X's acceptance | add inside it | optional `X.<step>` child; acceptance unchanged |
| Blocking prerequisite | explicit dependency | new deliverable `Y` (if independently verifiable) or external; X `blocked` on `Y` |
| Unrelated defect / optional improvement | backlog | `fsa-task discover --backlog "<text>"`; not a row; reported at hand-back |
| Material scope change (new user-visible outcome, new risk class, more than the authorised scope) | user decision | `fsa-task wait` on the decision; continue independent work |
| Genuine new independently verifiable outcome inside authorised scope | new deliverable | `add` after plan → shown as "+1 added" |

"Material" for UCM means: crosses a carve-out, a deploy class, a migration, a wire contract, or anything the checkpoint's
`scope.out` names. The test of "inside X" is: would X's acceptance criteria fail without it?

### 7.3 Waiting

- `fsa-task wait --decision "<exact question>" --blocks S3,S4` marks those rows `blocked` with `user: <decision>`, logs it, sets
  the checkpoint blocker, and runs `team-board wait`.
- `stop_guard` releases a `Waiting on: you - …` trailer only when no deliverable is `pending`/`in_progress`/`verifying` without
  a block; otherwise it continues the turn once with "S5 is not blocked by this decision: continue it, or block it on the
  decision". Its existing 3-block fail-open stays.
- Silence is never approval: a row blocked on `user:` is unblocked only by a lead `set` that quotes the user (`--reason`).
- The pre-plan approval case (user asked to stop for approval, as in this task): rows are written `pending` and blocked on
  `user: approve plan`, so the dashboard and stop-guard agree that the session waits.

### 7.4 Session-start planning contract (full path only)

Before the first edit or dispatch, the lead writes once, in the existing structures:

| Item | Where |
|---|---|
| Requested outcome, scope in/out | checkpoint `goal`, `scope` |
| Authorization and pending decisions | checkpoint `approvals` (quoted), `blockers`; blocked rows |
| Source and repository state | checkpoint `evidence` (HEAD, dirty files of others) — identity is already auto-stamped |
| Known baseline failures | checkpoint `baseline[]` (new) |
| Deliverables + acceptance + required checks | rows + `fsa-task accept` |
| Dependencies, blockers, next step | `blocked` notes, checkpoint `next` |

Then `fsa-task plan` writes the plan marker. Proportionality: a single-deliverable change has one row and one or two checks;
only the next deliverable is detailed, later ones are one-line `pending` rows refined when they start. When the user's
request already authorises the work, the plan is recorded and execution continues — no approval pause. The light path is
unchanged: no ledger.

### 7.5 Resume after compaction, `/clear`, resume

- The existing recovery summary gains: deliverables with status, the last log event per open deliverable, required checks
  still unmet, and the pending decision. `skipped`/`canceled` leave the open list (fixes D8).
- Reconciliation, lead instruction: for each open deliverable, check repository state (commits, dirty paths, run results)
  and record the outcome with `set`/`check`; continue the existing row's next step. Never `add` a deliverable for work an
  existing row covers.
- Deterministic help: `add` refuses an existing ID unless `--update` is given, and never changes status through `add`
  (fixes D3). `add` warns when a new title closely matches an open row's title (simple token overlap, no model).

### 7.6 Walkthroughs, before → after

| Case | Today (3.66.0) | Proposed |
|---|---|---|
| **Implementation, then a required test fails** | `S2` done "Codex done; awaits V2"; V2 fails; new row `S2r1` "S2 restart tests"; progress 3/3 → 4/4 (chatbot-standalone). | `S2` → `verifying` at dispatch finish; `check S2 runtime fail` keeps it `in_progress`; repair brief `TASK: …#S2.r1` (or note only); `check pass`; `set done --evidence`. Progress 0/1 → 1/1, repairs 1. |
| **Missing necessary step discovered** | New row "S4e add migration" counted as a deliverable. | Added as `S4.e` child (or in the note); acceptance unchanged; S4 cannot be done until `S4.e` closes. Deliverables unchanged. |
| **Unrelated defect** | Row `D01` "Dashboard: panel stops at legend" added to the UCM chatbot ledger and done. | `fsa-task discover --backlog "dashboard panel overflow (plugin)"`; reported at hand-back; fixed only in its own repository's ledger when the user asks. |
| **Blocking prerequisite** | Work proceeds in a row that silently waits, or a follow-up row appears later. | New deliverable `P1` (independently verifiable) or external dependency; `S3` `blocked` "on P1"; independent rows continue. |
| **Genuine scope expansion** | Rows `A01`, `I01`, `V2F` appended; total grows, looks like progress. | Material → `fsa-task wait --decision "Add Infobip import to this task?"` (no `--blocks`: it records the pending decision only); continue authorised work; on approval `add I01` → "+1 added after plan", quote logged. |
| **Resume after compaction / clear** | Summary lists rows; lead may re-`add` the plan, which overwrites statuses (D3); `skipped` rows listed as open. | Summary lists deliverables, unmet checks, pending decision; `add` of an existing ID refused; lead reconciles each open row against git and runs, then continues the next step. `/clear` still needs the user's `adopt`. |

## 8. Where each rule lives

| Deterministic code | Lead instructions | Possible future Jev classifier (advisory only) |
|---|---|---|
| done gate, reopen reason, check results, `verifying`, dot-ID children, counts, task log, `add` duplicate refusal, phase-complete refusal with open rows, stop-guard wait release only when open work is blocked, recovery open-row fix | deciding acceptance and required checks; classifying a discovery; recognising a material scope change; judging baseline vs regression; reconciling after resume; proportional planning | suggest a discovery class; flag a likely duplicate deliverable; flag a reply that asks for approval already given; flag a `done` note that mentions pending work ("awaits", "pending") |

Correct lifecycle enforcement needs only the first column. Jev output would be a hint written to the log, never a gate.

Permanent project conventions suggested for UCM `CLAUDE.md` (bindings only; dynamic state stays in ledgers):
- "Deliverables are rows; repairs stay inside their deliverable (note or `.rN` child)."
- "UCM material scope change = a carve-out path, a new deploy class, a migration, or an OpenAPI change not in the plan."
- "Baseline failures are recorded in the checkpoint before the first implementer batch."

## 9. Implementation units (independently testable) [P]

Each unit ships behind no flag; legacy ledgers keep today's behaviour. Order respects dependencies.

| Unit | Scope | Files | Test |
|---|---|---|---|
| L1 | Task log section + `add` duplicate refusal/`--update` + recovery open-row fix (D3, D8) | `scripts/lib/task_tracking.py`, `scripts/lib/task_recovery.py` | `tests/dashboard/test_task_tracking.py`, `test_task_recovery.py` |
| L2 | `verifying` status, dot-ID children, done gate, reopen reason, `check`/`accept`, dispatcher finish → `verifying`, refuse `done` rows (D2, D9) | `task_tracking.py`, `scripts/lib/task-row.sh`, Codex `tasks.py` | `test_task_tracking.py`, `scripts/lib/task-row.test.sh`, `tests/codex` |
| L3 | Counts: deliverables vs steps vs repairs vs added (D4) | `task_tracking.py` `_summary`, `scripts/lib/dashboard.html` | `test_task_tracking.py`, `test_information_ui.py` |
| L4 | Phase complete refused with open deliverables; dashboard phase consults the ledger (D5, D6) | `scripts/team-board`, `hooks/auto-phase`, `scripts/fsa-dashboard` | `hooks/team-board.test.sh`, `hooks/auto-phase.test.sh`, dashboard tests |
| L5 | `fsa-task wait`/`discover`/`plan`; stop-guard release rule (D7) | `task_tracking.py`, `scripts/lib/stop_guard.py` | `tests/codex/test_integration.py` (stop-guard cases), new stop-guard cases |
| L6 | Checkpoint `baseline[]`; recovery shows deliverables, unmet checks, pending decision | `scripts/lib/task_checkpoint.py`, `task_recovery.py` | `test_task_checkpoint.py`, `test_task_recovery.py` |
| L7 | Instructions: rewrite granularity rule, discovery table, planning contract, waiting, resume reconciliation | `task-tracking.md`, `SKILL.md`, `skill-guide.md`, `fullstack-agent.md`, Codex bundle | bundle render check; `diff --check` |

Each code unit also runs the full existing suites: `python3 -m unittest discover -s tests/dashboard -v`,
`python3 -m unittest discover -s tests/codex -v`, and `bash plugins/fullstack-agents/hooks/<name>.test.sh` for touched
hooks (commands from `docs/TASK_CHECKPOINT_RECOVERY_DESIGN.md:405-407`).

## 10. Verification plan [P]

Scenario tests (unit level, temp git repo fixtures as the existing ledger tests use):

| # | Scenario | Expected | Proves |
|---|---|---|---|
| T1 | X has check `unit`; `check fail`; `set done` | refused naming `unit` | X cannot be done while required verification fails |
| T2 | X done; later `check X unit fail` | X → `in_progress`, log reason, deliverables done count −1 | reopen, no new row |
| T3 | X gets `X.r1`, `X.r2` children, both done; X done | deliverables 1/1, repairs 2 | repairs do not inflate completed count |
| T4 | After `plan`, `add Y` | "1/2 (+1 added after plan)", log line for Y | genuine new deliverable recorded transparently |
| T5 | `check unit baseline` with matching `baseline[]` entry; `set done` | accepted; without entry → refused | baseline vs regression |
| T6 | `check unit unavailable`; `set done` | refused; `accept --drop unit` without `--reason` refused; with reason accepted and logged | unavailable check not silently passed; criteria weakening visible |
| T7 | `add` existing ID without `--update` | refused; status unchanged | resume cannot duplicate or overwrite |
| T8 | X blocked on Y; Y done | X still blocked until lead unblocks; `show` lists X dependency satisfied | dependency handling |
| T9 | `wait --blocks S3`; S4 pending; stop with `Waiting on: you` | stop-guard continues once naming S4; with S4 blocked → released | waiting only when dependent work is blocked |
| T10 | open deliverable; `team-board phase complete`; push hook | refused / skipped | session cannot look done with open rows |
| T11 | dispatcher finish on a `done` row | row unchanged, warning on stderr | no silent reopen |
| T12 | recovery render with `canceled` row | not in open rows | D8 |
| T13 | legacy 4-col ledger without dots/log | counts and statuses identical to 3.66.0 | compatibility |

Each non-trivial test is proven by removing its production line (policy profile rule).

Evaluating the effect (no paid experiments in this phase):
- Baseline now, from existing ledgers [H]: ratio of rows to deliverables (checkpoint ledger 27:~9), repair rows after a
  `done` (9 + 5 + ≥1 in three ledgers), `done` rows whose note says "awaits"/"pending" (2 in chatbot-standalone).
- After rollout, over the next ledgers: same three numbers from the task logs, plus reopen events (expected to replace
  repair rows), "added after plan" counts, and approval-wait replies from `classifier.jsonl` whose preceding prompt was an
  approval in the stop-guard state (re-asks). Success: repair-as-new-deliverable rows → 0; `done` with pending-work notes → 0;
  deliverable counts stable while repairs are visible; approval re-asks not above today's rate.
- Optional, only with your approval and a budget: one scripted replay session on a fixture repo with a planted failing test.

---

## 11. Amendments (user review, 2026-10-20) — supersede §3–§9 where they differ

Status: amendments recorded; revised implementation boundary **L1′** proposed and awaiting approval. Nothing implemented.

### 11.1 Format versioning, compatibility and rollback

- A ledger is **legacy** (today's 4- or 7-column header) or **v2** (8 columns:
  `ID | Status | Task | Note | Owner | Activity | Active until | Parent`). The header is the version marker.
- Legacy ledgers behave exactly as in 3.66.0 except for two defect fixes that apply to every format: duplicate IDs are
  refused (§11.3) and recovery stops listing `skipped`/`canceled` as open. No task log, no `verifying`, no gates, no parents.
- Upgrade is explicit: `fsa-task upgrade` rewrites the header to v2, leaves every Parent cell empty (every historical row stays
  a deliverable; nothing is inferred from `-R1`, `r1` or dots), and starts the task log with an `upgrade` event.
  `init` creates v2 unless `--format legacy` is given (decision for the user, §11.9).
- Compatibility: 3.66.0 readers reject the v2 header (`task_tracking.py:144-145`), so an old dashboard shows an error, an old
  stop-guard sees no rows and fails open, and old Codex `phase.py` refuses `complete`. Nothing old reports v2 work as done.
- Rollback: `fsa-task downgrade` (shipped with v2) converts only losslessly; see §11.12. Run it before reinstalling an
  older release; otherwise edit the header by hand (outside enforcement).

### 11.2 Parents and steps

- Parent is the explicit v2 column; the dot-ID form (`S4.r1`) is permitted, not interpreted. `add --parent S4` must name an
  existing row without a parent (one level only), and the child is shown with its parent.
- Child rows are optional. A routine repair reuses the deliverable's row (note and log); a child row is for a separately
  tracked brief or check that the lead wants visible.
- Counts: deliverables = rows with no Parent, excluding `canceled`/`skipped` from the denominator; children are reported
  as steps and never change the deliverable count. Legacy: every row is a deliverable (today's count).
- A parent cannot move to `done` while any child is `pending`, `in_progress`, `verifying` or `blocked`.
- v2 dispatcher: never auto-adds rows (warns: add the row first), finishes `succeeded` as `verifying`, and leaves a `done`
  row untouched with a warning (reopen is the lead's logged act). Legacy dispatcher behaviour is unchanged.

### 11.3 Duplicate IDs

`add` validates the whole batch before writing: any ID already present (or repeated in the batch) refuses the call and
the file is byte-for-byte unchanged. The upsert feature is removed in all formats; changing a title uses
`set --title`. The dispatcher already checks existence before `add` (`task-row.sh:49-50`).

### 11.4 Completion evidence against acceptance (v2, unit L2)

- `fsa-task accept --id X` records acceptance items: `{id, text, check}` where `check` names a command-backed check or
  `manual` (review, visual check, document update), plus the deliverable's relevant `paths`.
- Stored in a fenced JSON block between `<!-- fsa:checks:start -->` and `<!-- fsa:checks:end -->` in the ledger, written only
  by the tool (same pattern as the checkpoint block).
- `done` is refused unless every acceptance item of X is satisfied by its latest result (§11.5). Evidence strings are
  recorded but never sufficient alone. Removing or changing an acceptance item needs `--reason` and is logged.

### 11.5 Check results and freshness (v2, unit L2)

- `fsa-task check --id X --item A2 --result pass|fail|baseline|unavailable|not_applicable --log <path> [--reason]` stores
  `{item, result, log, at, state, reason}`.
- `state` = HEAD plus a SHA-256 over the **contents** of X's relevant paths as they are now (tracked diff against HEAD plus
  untracked file bytes). The checkpoint's porcelain-status fingerprint (`task_checkpoint.py:41-45`) is not reused, because a
  second edit to an already modified file leaves porcelain status unchanged.
- An item is satisfied only by its **latest** result; a later `fail` always overrides an earlier `pass`. `pass` (or
  `baseline`) counts only while its `state` equals the current state of X's paths; otherwise `done` reports
  "unverified change since <check> at <time>". `unavailable` never satisfies an item. `not_applicable` needs a reason.
- Limits, stated in `show` and the docs: a shared checkout can change during a test run; the state comparison detects a
  change made after the result was recorded, not one made during the run (D6 rule unchanged). Paths not declared are not
  covered.
- A `fail` recorded on a `done` row reopens it to `in_progress` with the check as the logged reason.

### 11.6 Baseline attribution (v2, unit L2)

- Allowed at any time, including after work started: `check --result baseline --baseline-log <path> --baseline-ref <commit>
  --reason "<explanation>"`. The tool requires an existing baseline log file and a ref that resolves to a commit, and records
  both. It cannot judge the log's content; the lead's explanation is logged verbatim.
- A baseline result satisfies the item but is never shown as `pass`: `show` reports "done with N baseline failures", and
  the log keeps the original `fail`.

### 11.7 Waiting, blockers and session state (unit L3)

- `blocked` rows carry typed blockers, one or more per row: `user: <exact question>`, `row: <ID>`, `worker: <run id>`,
  `external: <condition>`. Stored in the checks block; `set --status blocked` on v2 requires at least one. A row may have
  several blockers; it becomes executable only when all are cleared.
- A row is **executable** when it is `pending`/`in_progress`, has no uncleared blocker, and no live worker lease. A
  `pending` row is authorised by being in the plan; a row awaiting authorisation is blocked on a `user:` question.
- Derived session state, shared by stop-guard, dashboard and recovery:
  `done` (no open rows) · `executable` (≥1 executable row) · `waiting_worker` (none executable; ≥1 running worker or `worker:`
  blocker) · `waiting_user` (none executable or running; ≥1 `user:` blocker) · `blocked` (only `row:`/`external:` blockers).
- Stop-guard on v2: continues the turn only in `executable`; in any other state the turn may end with or without a trailer,
  so it never forces a misleading message and never loops. A `Waiting on: you` trailer in `executable` state continues once,
  naming the executable rows (existing 3-block fail-open kept). Legacy ledgers keep today's stop-guard rule.
- Clearing a `user:` blocker requires `--reason` quoting the user; silence never clears it.

### 11.8 Shared rules, phase completion and push (units L1′ and L3)

- One module `scripts/lib/task_rules.py` owns: status sets per format, open/terminal sets, allowed transitions, counts,
  parent checks, and (L3) the derived session state. Ledger commands, close, stop-guard, recovery, dashboard and Codex
  `phase.py` import it; `build.py` copies it into the Codex bundle.
- L3: `team-board phase complete` refuses while the bound ledger is not `done`. The push hook declares `review`, never
  `complete`; completion comes only from the ledger state or the lead's explicit `phase complete` (light path, no ledger).

### 11.9 History

v2 commands append to `## Task log`: add, status change (with reason/evidence), title change, parent, upgrade, accept/check
(L2), blocker set/clear (L3), discover (L4). Lease and activity updates are not logged. The log is never rewritten by the
tool; when an append would exceed the ledger byte limit the command is refused with a message to close or split the ledger
(no silent folding). Direct Markdown edits (Edit tool, editor, git) bypass every rule: the tool documents this, and a
malformed v2 file is reported as an error, never as progress.

### 11.10 Discovery and backlog (unit L4, lightweight)

`fsa-task discover --text "<finding>" --class repair:<ID>|dependency:<ID>|backlog|scope` appends one bullet to
`## Discoveries` and one log line. Only `scope` requires a user decision (an L3 `user:` blocker); `backlog` bullets are
never counted. No child row is required for any class.

### 11.11 L1 review and revised boundary

L1 as first proposed is not independently safe: its task log would write into legacy ledgers (against "preserve legacy"),
and introducing `verifying` and Parent later would need a second format break. The smallest coherent first group is the
v2 format itself:

**L1′ — ledger format v2 and structural lifecycle**
1. `task_rules.py` (new): status sets per format, open/terminal, transitions, counts, parent rules.
2. `task_tracking.py`: v2 parse/render, `upgrade`/`downgrade`, `init --format`, `add --parent`, duplicate refusal (all
   formats), `set --title`, `--reason` for reopening a `done` row (v2), parent-done check, task log (v2), counts via rules.
3. `task-row.sh`: v2 dispatcher behaviour (§11.2); legacy unchanged.
4. `stop_guard.py`, `task_recovery.py`, Codex `phase.py`, `close`: open sets from `task_rules` (adds `verifying`; recovery fix).
5. `dashboard.html`: `verifying` icon/label; deliverables and steps shown separately.
6. `build.py`: copy `task_rules.py` into the Codex bundle.
7. `task-tracking.md`: v2 format, compatibility, rollback, granularity rule rewritten (repairs stay in their deliverable).

Not in L1′: acceptance/checks/freshness/baseline (L2), blockers/session state/phase/push (L3), discovery (L4),
recovery additions and lead-instruction rewrite beyond `task-tracking.md` (L5). L1′ is safe alone: it adds no gate that
depends on L2/L3; `done` on v2 without L2 is as permissive as today, but no less.

### 11.12 Approved decisions and implementation conditions (2026-10-20)

Status: L1′ approved for implementation; A and B are one integration boundary. L1′ is **format and basic lifecycle
enforcement only**: evidence-backed completion stays unfinished until L2, and nothing in v2 output may imply checks are
enforced.

1. `init` creates v2 by default; `init --format legacy` creates today's format.
2. `add` upsert is removed in both formats. Any duplicate ID (existing, or repeated within one call) fails the whole call and
   leaves the file byte-for-byte unchanged. Title changes use `set --title`.
3. Strict format detection: the header row must equal exactly the 4-column, 7-column or 8-column (v2) header. Anything else
   (unknown column, reordered, extra column, v2 header with a 4- or 7-cell row) is an error naming the expected headers;
   nothing falls back to legacy. A v2 file must also contain exactly one `<!-- fsa:log:start -->`/`<!-- fsa:log:end -->`
   pair, each marker on its own line, after the task table.
4. Parent references (v2): the parent must be an existing row of the same ledger whose own Parent is empty; a row cannot
   parent itself; one level only (a row that has children cannot be given a parent; a child cannot be a parent). With one
   level and set-once parents, cycles cannot form; the parser still rejects any file violating these rules. Parent is set
   only by `add --parent` and never changed afterwards.
5. Adding a child whose status is not terminal (`pending`, `in_progress`, `verifying`, `blocked`) under a parent that is
   `done`, `skipped` or `canceled` is refused with a message to reopen the parent first (`set --status in_progress
   --reason …`). Adding a terminal child (e.g. a recorded `done` step) under a done parent is allowed. Nothing reopens a
   parent implicitly.
6. A parent cannot become `done` while any child is open. Reopening a `done` row (v2) needs `--reason`.
7. Legacy behaviour is unchanged except: duplicate-ID rejection (2) and recovery excluding `canceled`/`skipped` from open rows.
   Legacy `_render` keeps its 4/7-column auto-width.
8. Downgrade refuses any lossy conversion: it fails while any row is `verifying` or has a Parent, naming those rows. When it
   proceeds, it rewrites only the table region, restores the width recorded by the `upgrade` log event (4 only when every
   Owner/Activity/Active-until cell is empty, else 7), keeps the task log section and its markers intact, and appends a
   `downgrade` event. The table region round-trips byte-exactly through upgrade → downgrade when no row changed; the log
   section remains, because history is never removed.
9. Mutations rewrite only the table region and append inside the log markers; every other byte of the file (prose,
   checkpoint block, ownership log, unrelated sections) is preserved.
10. The row-granularity rule in `task-tracking.md` changes in L1′ (repairs and checks stay in their deliverable, child
    rows optional); the broader lead-instruction rewrite stays in L5.

---

## 12. L2 — evidence-backed completion (proposed 2026-10-20, awaiting approval)

Status: **proposed; nothing implemented.** Supersedes §11.4–§11.6 where they differ. Applies to v2 deliverables (rows
with no Parent) only. Legacy ledgers and steps are not gated. L1′ is accepted on its reported checks.

### 12.1 Pre-implementation findings

- Dispatcher failure paths, checked empirically under `set -euo pipefail` against a malformed v2 ledger, a ledger owned
  by another session and a deleted ledger: every hook only warns and the run reaches its cleanup; the foreign ledger is
  untouched. `result.json` is written before the ledger finish hook (`codex-task.sh` ~437 → `fsa_task_row_finish`), so run
  evidence never depends on the ledger. Gap: when `show` fails, the hooks fall back to legacy behaviour instead of
  disabling themselves (`task-row.sh` dispatch). L2 fixes that and adds no other dispatcher integration.
- The checkpoint fingerprint hashes `git status --porcelain` (`task_checkpoint.py` `fingerprint`): a second edit to an
  already modified file does not change it. L2 does not reuse it.

### 12.2 Storage

One tool-written block per v2 ledger, after the task log:
`<!-- fsa:evidence:start -->` + fenced JSON + `<!-- fsa:evidence:end -->` (same pattern as the checkpoint block).
It holds each deliverable's spec and its **latest** result per check; every result, spec change and attribution is also
one task-log line, so history survives while the block stays small. Run logs live outside the repository by default:
`$FSA_TASKS_DIR/evidence/<ledger-key>/<ID>-<check>-<UTC>.log`.

```json
{"schema": 1,
 "baselines": {"B1": {"command": "python3 -m unittest discover -s tests/codex", "failure": "test_x (known flaky)",
                       "log": "/abs/base.log", "log_sha256": "…", "ref": "<commit sha>", "recorded_at": "…"}},
 "deliverables": {
  "S4": {
   "kind": "code",
   "scope": {"paths": ["src/backend/crates/x/"], "inputs": ["Cargo.lock", "src/backend/.env.example"], "env": ["SQLX_OFFLINE"]},
   "automated_waiver": null,
   "criteria": [{"id": "AC1", "text": "Journey B restarts the bot", "checks": ["C1", "R1"]}],
   "checks": {"C1": {"method": "command", "command": "scripts/test-backend.sh -p x --test journeys", "cwd": "."},
              "R1": {"method": "review", "what": "diff read against brief ACCEPTANCE"}},
   "spec_at": "…",
   "results": {"C1": {"result": "pass", "started_at": "…", "finished_at": "…", "exit": 0,
                      "state_before": {"digest": "…", "head": "…", "files": 41}, "state_after": {"digest": "…", "head": "…", "files": 41},
                      "evidence": [{"path": "/abs/S4-C1-….log", "sha256": "…"}], "spec_at": "…", "reason": null,
                      "attributed": null}}}}}
```

### 12.3 Check methods and applicability

| Method | Proves | Required evidence |
|---|---|---|
| `command` | an automated test, build, lint or doc checker | exit code, log produced during the run |
| `review` | the lead's diff audit or a `diff-reviewer` lens | saved review notes or diff file |
| `inspection` | a visual check, live probe, rendered output | screenshot, probe log or output file |
| `document` | a design/doc deliverable is written and current | the document path itself (its hash is part of the state) |
| `analysis` | an investigation's conclusion | the report path with its cited sources |

Applicability is per deliverable `kind` (`code`, `docs`, `design`, `investigation`, `other`):

- Every deliverable needs ≥1 criterion, every criterion names ≥1 check, every check is used by a criterion.
- `code` needs ≥1 `command` check, unless `automated_waiver` holds a reason (logged) — e.g. a config-only change.
- `docs`, `design`, `investigation`, `other` never require a `command` check; a doc checker may be added as one.
- A non-`command` result needs ≥1 evidence file that exists; the tool cannot judge its content.

### 12.4 Commands (v2 only; legacy and steps refuse with a clear message)

| Command | Effect |
|---|---|
| `fsa-task accept --id S4 --input spec.json\|-` | Create or replace S4's spec. Validated against §12.3. Once any result exists, removing a criterion or check, changing a command/cwd, narrowing scope, or setting a waiver needs `--reason`; changing a check's definition invalidates its earlier results (`spec_at`). Logged as an `accept` diff. |
| `fsa-task check start --id S4 --check C1` | Records `started_at` and `state_before`; prints a token. |
| `fsa-task check finish --id S4 --check C1 --token T --result pass\|fail\|unavailable --evidence <path>… [--reason]` | Computes `state_after`, hashes evidence files (each must exist; a `command` log must have been modified after `started_at`), stores the result. |
| `fsa-task check run --id S4 --check C1 [--log P] [--timeout S]` | start → runs the recorded command with `bash -c` in its cwd, teeing to the log → finish. Exit 0 → `pass`; 124/timeout or 126/127 → `unavailable`; other → `fail`. |
| `fsa-task baseline --id B1 --command "<cmd>" --failure "<what fails>" --log P --ref <commit> --reason "<why baseline>"` | Ledger-wide known failure; log must exist, ref must resolve to a commit. |
| `fsa-task check attribute --id S4 --check C1 --baseline B1 --reason "<explanation>"` | Only on a latest `fail` of a `command` check whose command equals B1's. Result becomes `baseline`, keeps the failed result inside `attributed` and its original states (never restamped). |
| `fsa-task verify --id S4 [--json]` | Read-only gate report: what blocks `done`, per check. |
| `set --status done` (and `add` with status `done`) | Runs the gate; refused with the `verify` report. |

`unavailable` always needs `--reason`. There is no override flag: an unneeded check is removed with `accept --reason`,
which is logged and shown.

### 12.5 The gate (deliverable D)

`done` is refused unless all hold, checked under the ledger lock:

1. No open child step (L1′).
2. A valid spec exists (§12.3).
3. For every check used by a criterion, its latest result: exists; is `pass` or `baseline` (never `fail`/`unavailable`);
   was recorded at or after the check's current `spec_at`; has `state_before == state_after` (no change during the run);
   has evidence files that still exist with the recorded hashes; and has `state_after` equal to D's **current** state.
4. A `baseline` result's baseline entry still exists and its command matches.

On success the status changes and the log records which results were accepted. A `fail` recorded later on a `done`
deliverable reopens it to `in_progress`, logged with the check as reason (one row, never a new one). Staleness of a
`done` deliverable's evidence is shown by `show`/`verify` but does not reopen it on its own.

`show` (v2): `deliverables 3/5 done (1 with baseline failures) · verifying 1 …`, and per open deliverable a one-line
gate summary. Deliverables marked `done` before L2 (no spec) show "done, no recorded evidence".

### 12.6 State fingerprint (an evidence identifier, not a guarantee)

`state` of D = SHA-256 over a canonical list of `(path, content-sha256 | "missing")` for:

- every file under `scope.paths` that git tracks or that is untracked and not ignored (`git ls-files -co --exclude-standard`),
  including tracked files deleted from the working tree;
- every `scope.inputs` file, hashed by content even when gitignored (config such as `.env`, lock files);
- each check's resolved `cwd` and its command string;
- the values of `scope.env` variables as SHA-256 only (never stored in clear);
- HEAD is recorded for information but is **not** part of the digest: committing unchanged content keeps evidence
  current; a commit by anyone that changes scoped content makes it stale.

Bounds: scope paths must be inside the repository; more than 5,000 files or 200 MB hashed is refused ("narrow the scope").

**What it detects:** any net change to scoped content between start and finish (result unusable: "changed during
verification"), and any change between finish and `done` (stale). **What it cannot detect, stated in docs and `verify`:**
a change made and reverted inside the run window; changes outside the declared scope (shared crates, build caches,
toolchains, services, databases, other env vars); and a change in the instant after the gate passes. On a shared
checkout, another session's edits to scoped paths make evidence stale (conservative and correct); their edits elsewhere
are ignored by policy. The scope is the lead's declaration; too narrow a scope is the main residual risk, so `code`
deliverables should scope the crate/package, not single files.

### 12.7 Baselines

A baseline is recorded separately from passes and never turns into one: `show` counts "with baseline failures", the
attributed `fail` is kept in the result and the log, and the explanation is stored. Attribution may happen any time after
the failure, if a baseline entry exists for the same command. Whether the failure is truly the same one is the lead's
judgement (the tool records both logs and the reason).

### 12.8 Compatibility

- Legacy ledgers: unchanged; L2 commands refuse.
- v2 ledgers: the evidence block is optional until the first `accept`; L1′ readers treat it as prose.
- `downgrade` refuses while an evidence block exists (it would silently drop the gate), naming the command to inspect it.
- Direct Markdown edits bypass every rule; a malformed evidence block is a clear error for evidence commands and the gate,
  but `show`, `set` of non-done statuses and the dispatcher keep working (they do not need the block).
- Dispatcher: after a failed `show` it disables its hooks for that run; worker exit never records a result.

### 12.9 Files and units

- **E1** `scripts/lib/task_evidence.py` (new: spec validation, block load/splice, fingerprint, gate, command wiring);
  `task_tracking.py` (gate on `set`/`add` done, evidence subcommands registered, `show`/`verify` text, downgrade refusal,
  reopen on fail); `integrations/codex/scripts/build.py` (copy module); tests `tests/dashboard/test_task_evidence.py` (new).
- **E2** `task-row.sh` + `task-row.test.sh` (disable hooks after a failed `show`).
- **DOC** `task-tracking.md` "Completion evidence" section (lead writes).

### 12.10 Tests

| Case | Expected |
|---|---|
| No spec / criterion without check / code without command check or waiver | `done` refused, named |
| Missing result, `fail`, `unavailable` | refused |
| `pass` with current state | accepted; log lists accepted results |
| Scoped file edited (tracked, untracked new file, deleted, gitignored input, env value) after finish | stale → refused |
| Unscoped file edited | still accepted (documented policy) |
| File edited between start and finish (a command that writes a scoped file while running) | result marked changed during verification → refused |
| Commit of unchanged content after the pass | still accepted |
| Evidence log deleted or altered | refused |
| Log not written during the run (older mtime) | `finish` refused |
| `check run` exit 0 / 1 / 127 / timeout | pass / fail / unavailable / unavailable |
| Check command changed after its pass | old result invalid → refused |
| Removing a failed check without `--reason` | refused; with reason logged |
| Baseline attribution: matching command | `baseline` result, original `fail` retained, counted separately, accepted |
| Attribution with mismatched command / no baseline / on a pass | refused |
| `fail` recorded on a `done` deliverable | reopened to `in_progress`, logged reason; deliverable count drops by one, no new row |
| Repair: fail → fix → rerun pass | same row; deliverable total unchanged |
| `docs` deliverable with `document` + `review` evidence; `investigation` with `analysis` | `done` accepted without any command check |
| Worker success alone (row `verifying`, no results) | `done` refused |
| Old result is never restamped (state fields unchanged after later edits and commands) | asserted |
| Legacy ledger / step row | evidence commands refused; legacy `set done` unchanged |
| Malformed evidence block | evidence commands error clearly; `show` and non-done `set` still work |
| Dispatcher after failed `show` | hooks disabled; run cleanup and `result.json` unaffected |

Each non-trivial test proven by removing its production line. Suites afterwards: dashboard, codex, hook/script shell
tests, `git diff --check`.

### 12.11 Approved refinements (2026-10-20) — win over §12.1–12.10

Status: approved for implementation by headless Claude Sonnet (E1, E2; Codex window exhausted).

1. **Scope applicability policy.** `scope` = `{paths, dependencies, inputs, env, rationale}`. `dependencies` lists shared
   code the deliverable relies on (shared crates/modules, test helpers, fixtures, manifests, lockfiles); `inputs` lists
   configuration hashed even when gitignored. `rationale` (required) says why this scope covers what the checks exercise.
   `code` deliverables need ≥1 `dependencies` entry or `dependencies_none` with a reason. A package boundary is never
   assumed sufficient. Edits outside `paths ∪ dependencies ∪ inputs` are ignored by this declared policy, and `verify`
   prints the scope so the declaration is reviewable.
2. **Definition digest.** Each check has `definition_digest` = SHA-256 of: the check definition, `kind`, the whole
   `scope`, the waiver, and every criterion that references the check. Results store the digest from their run's start;
   a result counts only while it equals the current digest. Any `accept` that changes a digest after a result exists
   needs `--reason`; the log records which checks were invalidated.
3. **Outcomes.** `pass` (exit 0 and expectations met), `fail` (nonzero exit), `timeout`, `unavailable` (126/127, missing
   executable, infrastructure down — external finishes declare it with `--reason`), `inconclusive` (exit 0 but expectations
   unmet). Only `pass` and attributed `fail` satisfy the gate; `timeout`, `unavailable`, `inconclusive` always block and can
   never be attributed to a baseline.
4. **Expectations.** Every `command` check declares `expect`: `{"patterns": [regex…], "reject": [regex…]}` (all
   patterns must match the run log, no reject may match), or `{"none": "<reason>"}` for commands whose success is silent.
   Expectations apply to tool-run and external results alike. Criteria whose commands can pass vacuously should also name
   a `review` check; the tool does not infer that.
5. **Baselines.** `fsa-task baseline --id B1 --command "<cmd>" --ref <commit> --log P --signature "<text>"… --reason`:
   `ref` must be an ancestor of HEAD (it predates the work); the log must exist and contain every signature; the tool
   stores the log hash and the baseline code state (SHA-256 over `(path, blob id)` of the declared scope at `ref`, via
   `git ls-tree`). `check attribute --id S4 --check C1 --baseline B1 --reason` requires: the latest result is `fail` from a
   `command` check whose command equals B1's, its log contains every B1 signature, and B1's ref is an ancestor of HEAD. The
   `baseline` result embeds the original failed result (states, log path and hash), B1's provenance and the reason.
6. **External runs.** `check start` creates a run `{run_id (random 128-bit hex), deliverable, check, definition_digest,
   state_before, started_at, open}` stored in the evidence block. `check finish --run <id>` must match an open run of that
   deliverable and check whose digest is still current; a second finish, an unknown id, or a superseded definition is
   refused. Results carry `executor: tool | attested`; `verify` and `show` label attested results "attested, not executed
   by fsa-task".
7. **Result ordering.** The stored result for a check is the one with the latest `started_at`; on a tie a non-pass wins.
   Every finish (kept or not) appends a log line, so no result is lost. A non-pass finishing on a `done` deliverable reopens
   it with a logged reason.
8. **Self-invalidation.** The ledger file itself is never part of any state. Evidence files of `command`, `review` and
   `inspection` results must lie outside `paths ∪ dependencies ∪ inputs` (default log directory is outside the repository).
   For `document` and `analysis` checks the evidence is the subject file, which must be inside `paths`; its hash is taken at
   finish and a later edit makes the result stale by design.
9. **Concurrency.** Every evidence mutation runs under the ledger lock, re-reads the file, checks ownership, and writes
   atomically. The long-running part of `check run` happens outside the lock between start and finish. Two finishes are
   serialized; both are logged.
10. **Visible completion kinds.** `show`/JSON mark each done deliverable `completion: evidence | evidence_with_baseline |
    unrecorded` (done before L2 or upgraded); legacy rows carry none. Counts report them separately.
11. **Dispatcher.** A failed `show` prints a warning and disables every ledger hook for that run; cleanup and
    `result.json` are unaffected.
12. **Verification.** Focused mutation checks on the critical gate branches (stale state, run identity, attribution
    match, outcome mapping), not one per test.

### 12.12 As implemented (2026-10-20) — differences from §12.11 and known limits

- Baseline code state is SHA-256 over `git ls-tree -r --full-tree <ref>` (the whole tree at the ref), because baselines
  are ledger-wide and have no deliverable scope; it identifies the baseline code, it does not compare scopes.
- The state digest covers scoped content, inputs and env hashes only (not command/cwd as §12.6 said); each check's
  command, cwd and criteria are bound by its definition digest, so one check's change does not stale the others.
- Completion kind comes from a `completed` stamp written only when the gate passes, in the same atomic write as the status;
  every reopen path clears it. A deliverable closed any other way (before L2, via `upgrade`) shows *unrecorded*.
- Finished runs are removed from the evidence block (their result and log line remain); a second finish is "unknown run".
- `check run` launches the command in its own process group and kills the group on timeout.
- External finishes accept only `pass|fail|timeout|unavailable`; `inconclusive` is derived, `baseline` comes only from
  `attribute`.
- Malformed evidence block (repair r4): a reasoned reopen of a `done` deliverable succeeds, leaves the block bytes
  untouched for diagnosis and logs `evidence_malformed`; its stale `completed` stamp is irrelevant because completion
  kinds apply only to done rows and `done` again needs the gate, which needs a valid block.
- `_assert_fresh` allows 1 s of mtime jitter at the run start.

---

## 13. L3 — blockers, session state and truthful waiting (proposed 2026-10-20, awaiting approval)

Status: **proposed; nothing implemented.** v2 ledgers only for blockers and derived state; the legacy rules stay as today
except where §13.7 says otherwise.

### 13.1 Blocker records

A separate tool-written block `<!-- fsa:blockers:start -->` + fenced JSON + `<!-- fsa:blockers:end -->` after the task
log, so a malformed evidence block never stops blocker handling and vice versa.

```json
{"schema": 1,
 "blockers": {
  "Q1": {"kind": "user", "rows": ["S3", "S4"],
         "text": "Should the Infobip import run against the dev DB copy or a fresh fixture?",
         "why": "S3 seeds from the chosen source and S4 asserts its node count",
         "created_at": "…", "status": "open", "resumes": {"S3": "pending", "S4": "in_progress"},
         "resolution": null},
  "W1": {"kind": "worker", "rows": ["S5"], "text": "implement-20261021-…", "why": "S5's code is being written",
         "created_at": "…", "status": "resolved",
         "resolution": {"at": "…", "by": "tool", "evidence": "run implement-… state succeeded", "reason": ""}}}}
```

| Kind | `text` holds | Resolved by | Resolution evidence (required) |
|---|---|---|---|
| `user` | the exact question | `resolve --quote "<user's words>" --reason` | the quote (recorded, not authenticated) |
| `row` | the prerequisite row ID | automatically when that row is `done` through its gate | the row's `done_gate` log line |
| `worker` | run id or task name | `resolve --evidence <run id or log>`; the dispatcher resolves its own run's blocker at finish | run id + recorded state |
| `external` | the condition (CI, service, quota window) | `resolve --evidence <log or observation> --reason` | evidence path or text + reason |

`withdraw --reason` closes a blocker that turned out wrong (logged; never silent).

### 13.2 Commands and consistency (enforced)

- `fsa-task block --rows S3,S4 --kind user --text "…" --why "…"` creates the blocker, sets each row `blocked`,
  remembers its previous status in `resumes`, appends a log line. `why` is required for `user` (why it blocks progress)
  and recommended for the others.
- `fsa-task resolve --id Q1 (--quote …|--evidence …) --reason …` closes it; each row with no other open blocker returns to
  its remembered status (logged).
- A v2 row is `blocked` **iff** it has ≥1 open blocker: `set --status blocked` without one is refused (use `block`);
  `set` moving a row out of `blocked` while a blocker is open is refused (resolve or withdraw first). Steps may carry
  blockers; a deliverable's state also counts its steps' blockers.
- Different rows may wait on different questions; one row may wait on several blockers; it resumes only when all close.
- There is no timeout or default resolution: silence never resolves a `user` blocker.

### 13.3 Derived session state (one function, `task_rules.session_state`)

Computed from rows, blockers and leases, never from reply text:

| State | Condition (evaluated in this order) |
|---|---|
| `done` | no open deliverable or step |
| `executable` | ≥1 open row that is not `blocked` and has no live lease held by a worker (owner ≠ `lead`) |
| `waiting_worker` | none executable; ≥1 live worker lease or open `worker` blocker |
| `waiting_user` | none of the above; ≥1 open `user` blocker (directly, or at the root of a `row` chain) |
| `waiting_external` | none of the above; ≥1 open `external` blocker |
| `blocked` | none of the above (only `row` blockers whose chain has no root, e.g. a cycle or a canceled prerequisite) |

The state carries the lists that explain it: executable rows, open user questions (`id`, `text`, `why`, rows),
worker runs, external conditions. `executable` wins even while questions are pending: independent authorised work
continues, and the pending questions are still listed. Rows are treated as authorised by being in the plan; work the user
has not authorised is represented by a `user` blocker (lead instruction, not tool-verifiable).

### 13.4 Consumers (all call `session_state`)

- **Stop guard (v2):** `executable` → hold the turn, naming the executable rows (existing 3-continuation cap per
  unchanged ledger, so it never loops). `waiting_user` → release only when the final message names every open user
  blocker by id or quotes its question; otherwise one continuation: "state Q1: <text> — blocks S3, S4 because <why>".
  `waiting_worker`, `waiting_external`, `blocked`, `done` → release with no required wording. Trailers stay accepted but
  no longer decide anything on v2.
- **Board wait:** `block --kind user` and `resolve` keep `team-board wait` in sync with the open user blockers
  ("Q1: <text> (blocks S3, S4: <why>)"); the dashboard shows that text. Its reply classifier stays for sessions without
  a v2 ledger.
- **Phase completion:** `team-board phase complete` and Codex `phase.py complete` refuse unless `session_state` is `done`
  (v2) or no open rows remain (legacy, today's Codex rule now applied to Claude too). Sessions without a ledger are
  unchanged.
- **Push:** the `auto-phase` push hook declares `review` ("pushed <branch> at <sha>; completion not established by a
  push"), never `complete`, for every session.
- **Dashboard:** shows the derived state and its lists; a declared `complete` with a non-`done` ledger is shown as
  `review` with "ledger has open work".
- **Recovery summary:** lists open blockers (id, kind, text, why, rows) from the ledger, ahead of narrative checkpoint
  blockers.

### 13.5 Checkpoint integration

The checkpoint's `blockers` stays a narrative list. The ledger's blocker block is authoritative for state. `resolve
--quote` prints a reminder to record the approval in the checkpoint (`approvals[]`), whose rules stay unchanged: a recorded
approval is never an authorisation, and a resolved `user` blocker is the record that the specific question was answered.

### 13.6 Enforced vs advisory

| Enforced by code | Advisory (lead judgement, recorded) |
|---|---|
| blocker typing and required fields; `blocked` ⇔ open blocker; no unblock while open; derived state; stop-guard decision; phase-complete refusal; push → review; no automatic resolution of user blockers | whether a quote truly came from the user and answers the question; whether the `why` is accurate; whether an external condition really cleared; which rows are authorised; whether an answer is ambiguous (then keep the blocker open) |

### 13.7 Legacy ledgers

Blocker commands refuse ("requires a v2 ledger"). Stop guard keeps today's rule. `phase complete` now refuses while open
rows exist (parity with Codex). Push → `review` applies to every session. No derived state is shown beyond today's counts.

### 13.8 Units

- **L3a** `scripts/lib/task_blockers.py` (new: block I/O, commands, resolution, row-chain roots), `task_rules.py`
  (`session_state`), `task_tracking.py` (register commands; `set` consistency; summary `session_state`) — it is at 799
  lines, so the `set` evidence branch moves into `task_evidence.py` first (pure move, no behaviour change), `task_recovery.py`
  (blocker lines), `build.py`, tests `tests/dashboard/test_task_blockers.py`.
- **L3b** `stop_guard.py`, `scripts/team-board` (phase complete refusal; wait sync helper), `hooks/auto-phase` (push →
  review), `scripts/fsa-dashboard` + `dashboard.html` (state display), Codex `phase.py`; tests in
  `tests/codex/test_integration.py`, `hooks/auto-phase.test.sh`, `hooks/team-board.test.sh`, dashboard tests.
- **L3doc** `task-tracking.md` (blockers, waiting, completion), the `skill-guide.md` phase table rows for complete/push/wait.

### 13.9 Tests

| Case | Expected |
|---|---|
| Two rows blocked by two different user questions, a third row pending | state `executable` (third row); both questions listed; stop guard holds the turn |
| Third row done | state `waiting_user`; reply naming only Q1 → one continuation asking for Q2; naming both → released |
| Resolve Q1 with a quote | its row resumes its remembered status; Q2's row stays blocked; state `executable` |
| Resolve without quote/evidence; set unblock with an open blocker; set blocked without a blocker | refused |
| Row blocked on Q1 and on external E1; Q1 resolved | still blocked until E1 resolves |
| Only a live worker lease (dispatcher running) | `waiting_worker`; stop guard releases without forcing text |
| External blocker only (e.g. quota window) | `waiting_external`; released; listed in show/recovery |
| External check failure recorded as a blocker, later resolved with evidence | resumes; evidence and reason logged |
| Row chain S5 → S4 → Q1 | S5 counts as waiting on Q1 (root); cycle S6 ↔ S7 → `blocked` |
| No user activity for a long time | blocker stays open (no time-based resolution) |
| `phase complete` with open rows (v2 and legacy) / with done ledger / without ledger | refused / accepted / unchanged |
| `git push` hook on the default branch | phase `review` with the "completion not established" note, never `complete` |
| Dashboard: declared complete but ledger open | shown as review with "ledger has open work" |
| Stop guard repeated blocks on an unchanged ledger | released after the existing cap (no endless retries) |
| Legacy ledger | blocker commands refused; stop guard unchanged |
| Codex `phase.py complete` | same decision as Claude for the same ledger |

### 13.10 Reduced L3 boundary (after `docs/WORKFLOW_OVERHEAD_REVIEW.md`, 2026-10-20) — proposed

- Keep: typed blockers (§13.1) with required resolution evidence; `blocked` ⇔ open blocker; one `session_state` with
  precedence executable > waiting_worker > waiting_user > waiting_external; stop-guard rule (§13.4) with the existing cap;
  `phase complete` refusal (v2 and legacy); push → `review`; board wait synced from user blockers; recovery lists blockers.
- Drop: row-chain root analysis and the separate `blocked` cycle state (a row blocked on another row is shown with that
  dependency; if no open work is executable and only row dependencies remain, the state is `waiting_external` with the
  dependency listed); manual `team-board steps` and manual phase declarations other than `complete`/`review` when a ledger
  exists (review W2).
- Same release as L1′/L2 and the review's T1/T4/W1 changes (user: single release).

## 14. Continuity across execution limits (folded into reduced L3/L5; proposed 2026-10-20)

### 14.1 Observed case and causes

Session `d715e3ba` (2026-10-20 18:35Z) stopped with required runtime tests failing and Codex's 5-hour window at 100 %,
then advised `/clear` and pasting `tasks/chatbot-builder-k1.md`, calling a fresh session "cheaper per turn".
- **Model behaviour:** no plugin text recommends `/clear` below 85 %; the only trigger is `fsa-usage` `HANDOFF:` at 85 %
  ("write the handoff or compact", `scripts/fsa-usage:53-54`, cited by `agents/lead/fullstack-agent.md:158`). The cost
  claim was unsupported.
- **Design gap:** after `/clear` the old task is offered only within 300 s and in the same Claude process
  (`task_lifecycle.py` `_eligible_parked`, parked records pruned when the process exits or after 24 h), so after a quota wait
  and a restart the new session knows nothing and the path has to be pasted.
- **Missing state:** quota exhaustion had no representation; it surfaced as prose plus a request to the user.

### 14.2 Verified platform capabilities (Claude Code docs, checked 2026-10-20)

| Capability | Fact |
|---|---|
| Trigger `/compact`, `/clear` or any slash command from a hook | not possible ("can't trigger `/` commands or tool calls", hooks guide) |
| Inject context at SessionStart (`startup/resume/clear/compact/fork`) and UserPromptSubmit | supported (`hookSpecificOutput.additionalContext`) |
| Hook on an external tool's quota (Codex) | not documented; Claude's own API limits only (`StopFailure` `rate_limit`, `autoContinueAtUsageLimit`) |
| Same-session one-shot later prompt | `CronCreate` (session-scoped, no setup; does not fire while Claude Code is not running; missed fires not caught up) |
| Auto-compaction | automatic at the context limit, configurable (`autoCompactWindow`); PreCompact can block, cannot customise the summary |
| Stop-hook loops | Claude Code overrides after 8 consecutive continuations; `stop_hook_active` exposed |

Consequence: the plugin cannot clear, compact or restart a session, and cannot be woken by Codex's reset. It can record
the state, refresh the checkpoint, and tell the next prompt or session exactly where the task stands.

### 14.3 Folded into reduced L3/L5 (no new mechanism beyond these)

1. **Capacity is an `external` blocker** with `class: capacity` (`infrastructure`, `other` for the rest), naming the engine
   and `until` from `plan_usage` `resets_at` when known. It is not a user question. A `user` blocker exists only if the lead
   wants an engine switch that is not already authorised.
2. **Independent work continues:** `executable` outranks every wait (§13.3).
3. **Automatic checkpoint at handoff:** `block` and `resolve` refresh an existing checkpoint's `blockers` and `next` from the
   ledger in the same validated write (failing checks come from L2 results). With no checkpoint, the ledger plus its L2
   results is the record; the tool never invents goal or scope. The deliverable stays open with its failing checks.
4. **Same-session continuation:** the existing UserPromptSubmit hook adds one line when the bound ledger is not
   `executable`: state, open blockers, failing checks, next action; for a capacity blocker whose `until` has passed:
   "check `fsa-usage` and resolve E1 with its output". It never resolves anything itself. No path is asked of the user.
5. **New session after `/clear` or restart:** SessionStart (`startup`, `clear`) lists up to three resumable ledgers in
   this checkout (open rows, active checkpoint, owner free or stale) from the ownership records, with no 300 s limit. It
   never binds. Only a user instruction to continue that task (e.g. "continue the previous task") supplies adoption intent;
   the lead then runs `fsa-task adopt --file <listed> --from <listed owner>` (plus `--takeover` for a stale owner, the
   user's instruction being the direction). A generic new request starts fresh. With several candidates the lead asks which.
6. **No reset advice:** the lead prompt and `fsa-usage` stop suggesting `/clear` or a fresh session. `HANDOFF:` becomes
   "write the checkpoint now; automatic compaction keeps the task and its recovery summary". Recommending `/clear` needs a
   reason other than context percentage or cost.
7. **Approval boundaries survive recovery:** recovery and the continuation line repeat that recorded approvals are not
   authorisations; database resets, migrations, reloads and releases need a fresh go-ahead.

### 14.4 Separate proposal (not in this release candidate)

Quota-aware wake-up: when a capacity blocker has a known `until` and nothing else is executable, the lead may offer,
and with the user's yes create, one `CronCreate` one-shot in the same session at `until`, whose prompt is "check capacity;
if available, resolve E1 and continue". Limits: only while Claude Code keeps running; no catch-up; no polling. This adds
a scheduling behaviour, so it stays out until approved separately.

### 14.5 Added tests (isolated fixtures, no paid probes)

| Scenario | Expected |
|---|---|
| S2's required check failing, `external/capacity` blocker on S2 ("codex", `until` set), no other open work | state `waiting_external`; stop guard releases without a forced question; S2 not done; checkpoint `blockers`/`next` refreshed and valid |
| Same, plus an unblocked pending S3 | state `executable`; stop guard holds, naming S3 |
| Next prompt in the same session after `until` passed | continuation line names E1, the failing check and "resolve with fsa-usage output"; no state change |
| `resolve` E1 with free text only | refused; with an `fsa-usage` output file → resumes S2's remembered status |
| `/clear` then generic request | SessionStart lists the ledger; nothing bound; the ledger stays owned/parked |
| restart after 2 h, then "continue the previous task" | candidate listed without the 300 s window; `adopt` restores the binding; recovery summary shows S2, E1, the failing check and next action; no plan rebuilt |
| Recovery of a ledger whose checkpoint records a DB-reset approval | summary marks it as a record, not an authorisation |
| `fsa-usage` at 54 % / 86 % | no reset advice / "write the checkpoint now" without `/clear` |

### 14.6 Approved refinements and implementation decisions (2026-10-21)

Approved: Sonnet for this release candidate's remaining code units; reduced L3 (§13.10) + limited L5 + §14.3 with:
1. **Capacity blocker** (`external`, `class: capacity`, `engine`, `until`, optional `offer`, e.g. "switch to Sonnet if you
   authorise it"). An offer is information, not a question: the state stays `waiting_external`. `resolve` of a capacity
   blocker reads the engine's actual window through `plan_usage` (cached data, no network in hooks): refused while the
   window reports ≥ 100 % or when capacity is unknown unless `--evidence <file> --reason` records a manual observation.
   Time passing alone never resolves it.
2. **User blockers** resolve only with `--quote` that occurs (whitespace-normalised, ≥ 8 characters) in a user prompt
   recorded for this session by the UserPromptSubmit hook (`prompt_history`, bounded, local state dir). `worker` needs a
   run `result.json` path with a `state`; `external` needs an existing evidence file and a reason. `withdraw` needs a reason.
3. **Checkpoint refresh** on `block`/`resolve`/`withdraw` when a valid checkpoint exists: `blockers` = open blocker lines,
   `next` = the blocker's `--next` when given. An invalid checkpoint is reported, never rewritten; the ledger change stands.
4. **Same-session continuation:** the UserPromptSubmit hook adds one line for a bound v2 ledger that is not `executable`
   or has open blockers (state, blockers, failing checks, next action, and after `until` "check capacity with fsa-usage
   before resolving"). Uses the existing binding; never asks for a path.
5. **After clear/restart:** `fsa-task candidates --cwd` and the SessionStart line list ledgers of the same canonical
   checkout with open rows, a valid ledger, a checkpoint that is absent or `active`, and an owner that is free or stale
   (never live/unknown); most recently modified first; three shown plus "N more (fsa-task candidates)". Each line carries
   the exact `bind` (free) or `bind --takeover <owner>` (stale, on the user's instruction) command. Nothing binds
   automatically. "Continue the previous task" with one candidate adopts it; with several, the lead asks which.
6. **Authorisation continuity:** checkpoint approvals never create or widen authorisation; clear, restart or compaction
   does not revoke one. Reconfirm only when scope changed, a stated limit expired, a single-use approval was consumed, or
   the approval cannot be established from the user's words. Database resets, migrations, reloads and releases keep their
   explicit-approval rule.
7. **Advice:** `HANDOFF:` → "write the checkpoint now; automatic compaction summarises the conversation, so reread the
   ledger, checkpoint and authoritative files when needed". No `/clear` or cost advice.
8. **T1/T3/T4/T9/W1:** the options recommended earlier (T1 i–iii plugin-side only with UCM binding text as a proposal;
   T3 per-group checks, `check run` default timeout 540 s, sequential Cargo groups; T4 rewrite; T9 `AFFECTED_TESTS:`;
   W1 tags on `ACCEPTANCE:` items, `DEPENDS:`/`INPUTS:`/`ENV:`/`SCOPE_WHY:`/`KIND:`, `accept --from-brief` run by the lead,
   union-only merge for repair briefs).
9. Out: `CronCreate` wake-up, scheduled prompts, polling, automatic clear/restart.

Units: U1 blockers + session state (first); then in parallel U2 consumers (stop guard, phase complete, push, Codex
phase), U3 continuity + recovery, U4 brief→evidence + check timeout, U5 dashboard; lead writes the instruction docs.
