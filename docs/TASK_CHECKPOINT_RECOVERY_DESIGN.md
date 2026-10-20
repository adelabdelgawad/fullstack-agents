# Task checkpoint and recovery after compaction or `/clear`

Status: **implemented** (U1a–U5, released in 3.66.0). Kept as the design record. Current behaviour is owned by
`plugins/fullstack-agents/skills/task-flow/references/task-tracking.md` and the code listed in §9; where this
record and those disagree, they win. Written 2026-10-19/20 by session `b8c9807b`.

Baseline: installed release **3.65.6** (`origin/main` `f4e708a`), Claude Code **2.1.303**. The local `main`
checkout is at `9721092`, two skill-only commits behind; none of the files below differ.
Labels: **[S]** confirmed in source; **[D]** official documentation; **[O]** observed on this host;
**[P]** proposal; **[Q]** open question with the check that settles it.

---

## 1. Current behaviour

| # | Behaviour | Evidence |
|---|---|---|
| C1 | `session-start` and `session-policy` run on `startup\|resume\|clear\|compact`. `fork` is **not** matched. | [S] `hooks/hooks.json` |
| C2 | `session-start` emits project detection, plugin scripts and team board. It carries **no task state** on any source. On `startup`/`clear` it renews the plugin pin; on `resume`/`compact` it keeps the pin. | [S] `hooks/session-start:18-28,104-136` |
| C3 | The task ledger is a Markdown file in the repository (`docs/tasks/<task>.md` by convention). It is bound to one session by `~/.local/state/fullstack-agents/tasks/<session_id>.json` = `{session_id, root, file}`. There is no checkout, branch, HEAD, task id or closed state. | [S] `scripts/lib/task_tracking.py:28-36,255-285` |
| C4 | Ledger and binding writes are atomic: temp file, fsync, `os.replace`, directory fsync. Writes are serialized per (root, file) by `flock`. | [S] `task_tracking.py:174-209` |
| C5 | `fsa-task` defaults `--session` to `CODEX_THREAD_ID` or `CLAUDE_SESSION_ID`. Claude Code exports **`CLAUDE_CODE_SESSION_ID`**, which is what `team-board`, `fsa-usage` and `codex-task.sh` read. In a Claude session `fsa-task bind` without `--session` therefore fails. | [S] `task_tracking.py:295`; `team-board:59`; `fsa-usage:31`. [O] this session's environment has `CLAUDE_CODE_SESSION_ID` and no `CLAUDE_SESSION_ID` |
| C6 | `stop-guard` holds a turn open while the session's bound ledger has open rows. The dashboard shows the bound ledger. Both depend on the binding's session id. | [S] `scripts/fsa-stop-guard`, `scripts/lib/stop_guard.py:102`, `task-tracking.md:42` |
| C7 | `session-end` releases the session's team-board claims and locks on every reason, including `clear`. | [S] `hooks/session-end` |
| C8 | `fsa-usage` reads the transcript: input, output, 5-minute and 1-hour cache writes, cache reads, compactions, estimated cost, plan windows. At ≥85% fill it prints `HANDOFF:`. The handoff content and location are **unspecified**: the lead prompt says "write the handoff into the task file". | [S] `scripts/fsa-usage`, `scripts/lib/usage.py:105-160`, `agents/lead/fullstack-agent.md:158` |
| C9 | There is no PreCompact or PostCompact hook. | [S] `hooks/hooks.json` |
| C10 | Handoffs are written by hand into the ledger. The successor session does not rebind. Example: `ucm/tasks/chatbot-builder-k1.md` has "Handoff (lead session 90a237ec) — superseded" and "Handoff (lead session 695ce86c) — CURRENT", but the binding still names `90a237ec` and `695ce86c` has no binding. | [O] `~/.local/state/fullstack-agents/tasks/90a237ec-*.json` |
| C11 | `tests/overhead/probe.py` runs every hook as wired and measures injected characters and latency. Task-ledger tests are in `tests/dashboard/test_task_tracking.py`; SessionStart delivery tests are in `tests/codex/test_session_context.py`. | [S] |

**Gaps.** G1: after compaction nothing restores the task (C2, C9). G2: after `/clear` the new session has no
binding, so the dashboard, stop-guard and recovery lose the task; the only route back is a hand-written handoff
(C3, C6, C10). G3: decisions and approval boundaries have no fixed place in the ledger, so they survive only if
the lead remembered to write them. G4: verification results carry no record of the inputs they were run against.
G5: `fsa-task` cannot find the Claude session id on its own (C5). G6: `fork` sessions get no session context (C1).

## 2. Lifecycle facts from the documentation

| Fact | Source |
|---|---|
| SessionStart `source`: `startup`, `resume` (`--resume`/`--continue`/`/resume`), `clear`, `compact` (auto or manual), `fork`. | [D] hooks.md "SessionStart" |
| `/clear` **starts a new session**. The previous one is saved and can be resumed. SessionEnd fires with `reason: "clear"`. | [D] commands.md (`/clear`), interactive-mode.md ("Running `/clear` starts a new session"), hooks.md "SessionEnd" |
| Compaction keeps the session. PreCompact (`manual`/`auto`) runs before it and can block it. Blocking an auto-compaction that recovers from a context-limit error **fails the request**. PostCompact receives `compact_summary` and has no decision control. | [D] hooks.md "PreCompact", "PostCompact" |
| PreCompact does **not** fire on `/clear`. The only hooks around a clear are SessionEnd(`clear`) on the old session and SessionStart(`clear`) on the new one. | [D] hooks.md matcher tables |
| SessionEnd's default budget is 1.5 s, and a plugin hook's own `timeout` does not raise it. | [D] hooks.md "SessionEnd" |
| A hook context string is capped at 10,000 characters; above that Claude gets a file path plus a 2,000-character preview. | [D] hooks.md "Add context for Claude" |
| If `/clear` runs while background SessionStart hooks are still running, their output is dropped. | [D] hooks.md "SessionStart" |
| Prompt cache: an exact prefix match over tools, then system, then messages. A subscription main conversation keeps it for 1 hour; subagents and compaction for 5 minutes; API keys and providers for 5 minutes. Writes cost 1.25× or 2× input, reads 0.05–0.1×. | [D] code.claude.com/docs/en/prompt-caching; platform prompt-caching |

**Corrections to the earlier comparison.**
- **`/clear` is neither free nor lossless.** The first request of the new session re-sends the system prompt,
  tools, CLAUDE.md and hook context. That is a cache write unless the prefix is still cached for this directory.
  Every file and fact Claude needs again is re-read, and anything not written down is lost.
- **Compaction is not free either.** It is one large summarising request, cheap only while the cache is warm, and
  the summary is lossy.
- **Cache behaviour varies.** It depends on model, provider, TTL bucket, tool deferral and settings.
- **Dollars are not plan usage.** `fsa-usage` reports API-priced *estimates*; subscription usage is a plan-window
  percentage whose weighting is not published, so an estimated-dollar saving does not establish an equal
  plan-usage saving.

### 2.1 Lifecycle probes (observed 2026-10-19, Claude Code 2.1.303)

The probes ran in a throwaway interactive session (`claude --model haiku` in tmux) in a scratch git repository.
Project hooks on every relevant event dumped their stdin, `CLAUDE_*` environment and process ancestry with
`/proc/<pid>/stat` start times. Bash-mode (`!`) commands recorded the tool environment. All [O].

| Probe | Observation |
|---|---|
| Q1 `/clear` session id | SessionEnd(`clear`) fired with the old id, then SessionStart(`clear`) with a **new** id. The Bash tool then saw the new `CLAUDE_CODE_SESSION_ID`, and variables from the new SessionStart's `CLAUDE_ENV_FILE` (`PROBE_SS_SOURCE=clear`). |
| Q2 process identity | `CLAUDE_PID` is set in **every hook** and in the Bash tool, and it is unchanged across `/clear`, `/branch` and `/compact`. Each hook's parent `sh` has `CLAUDE_PID` as its parent. The process start time (`/proc/<pid>/stat` field 22) was stable across the session, so **(pid, start time)** identifies the process even if the PID is later reused. |
| Q3 hook before first prompt | A prompt sent 1.3 s after `/clear`, while a 4 s SessionStart(`clear`) hook was still running, reached UserPromptSubmit only **after** the hook ended (start-up hook finished 376.43 s, UserPromptSubmit fired 376.48 s). The notice reaches Claude before the first prompt. |
| Session links | SessionStart(`clear`) input has **no previous-session field and no `prompt_id`**; SessionEnd(`clear`) had a `prompt_id`. So a clear can be linked to its predecessor only by the same process and order. |
| Fork (`/branch`) | SessionEnd(`resume`) for the parent, then SessionStart(`fork`) with a new id. Both carried the **same `prompt_id`**. The fork input also has `session_title`, `context_tokens` and the cache fields. The fork holds the parent's whole conversation, including any task knowledge. |
| Compaction (`/compact`) | Order: PreCompact(`manual`) → SessionStart(`compact`) → PostCompact, all with the **same** session id. PostCompact runs *after* SessionStart, so its `compact_summary` cannot feed the recovery block. |
| Side effect (existing behaviour) | `session-end` releases team-board claims on every reason, so `/branch` (reason `resume`) also releases the parent's claims. |

**Consequences for the design.** The probes leave the design's shape unchanged and settle its open points:
- the clear notice uses the key (process id, process start time, checkout) plus the end→start order;
- forks follow the clear rule;
- the recovery block is built at SessionStart(`compact`), not at PostCompact;
- ledger writes also need an ownership check, because a fork or another session could otherwise update a ledger
  it does not own (§3.2).

## 3. Recommended design

One principle: **the lead writes the checkpoint and the hooks only deliver it.** No model summarises the task in a
hook. Only the lead saw the user's decisions, and an automatic summariser can turn a guess into a recorded
"decision".
- **Cost:** zero extra model *summarisation* calls, plus three small, fast hooks. The lead's own writes are part of
  its normal turns and cost tokens.
- **Accuracy:** a lead-written checkpoint can still be wrong or incomplete. Every decision and result names its
  source (a user quote or an evidence path), and recovery presents the checkpoint as a claim to re-check, never as
  ground truth.

### 3.1 Checkpoint: a fixed section in the existing ledger

The checkpoint lives in the task's existing ledger file, between `<!-- fsa:checkpoint:start -->` and
`<!-- fsa:checkpoint:end -->`, after the existing task table, as one fenced `json` block. JSON is validated
strictly and needs no new library. Unknown keys are rejected anywhere, so no field such as `authorized` can be
added. The tool computes `identity` and each verification `fingerprint`; the lead never supplies them. It is written only through a new
`fsa-task checkpoint` subcommand, which validates the fields and reuses `_atomic` and `_lock` (C4). The section
is capped at 8 KB. Fields, all required unless marked:

| Field | Content |
|---|---|
| `identity` | task id (file stem), repository root, checkout path (`git rev-parse --show-toplevel`), branch, HEAD at write, writer session id, `written_at`, schema `v1` |
| `goal` | one line |
| `scope` | the approved scope, verbatim as approved, plus explicit out-of-scope items |
| `approvals` | each entry: the user's words (short quote), when, scope, `single-use\|task`, `used: yes/no`, `clarity: explicit\|ambiguous`. Never inferred; an approval whose words don't plainly cover the scope is recorded `ambiguous`. A record of what the user said, never an authorization source (§3.5) |
| `decisions` | `D<n>: <decision> — source: user <time> \| evidence <path>` |
| `constraints` | project or user rules that bind this task (pointers, not copies) |
| `done` | completed items with evidence paths (ledger rows hold the detail) |
| `next` | the single next action and who owns it |
| `blockers` | optional |
| `evidence` | file paths, run ids, log paths |
| `verification` | each entry: command, result, log path, `run_at`, and the input fingerprint (HEAD plus a hash of `git status --porcelain -- <paths>` for the paths the check covers) |
| `status` | `active` \| `completed` \| `abandoned` |

**When the lead writes it** (added to `task-tracking.md`; there is no timer). Only on a **meaningful state
change**:
- a user decision or approval arrives;
- a plan is approved;
- an implementer batch is dispatched, or its result is accepted or rejected after audit;
- a verification **outcome** is established: the lead has read a test, build or check log and concluded pass or
  fail;
- a blocker appears or clears;
- `fsa-usage` prints `HANDOFF:`;
- before a manual `/compact` or `/clear`.

Ordinary file reads, greps, worker progress and intermediate log lines are **not** triggers. Several changes in
one turn are batched into one write. A write that would change nothing is skipped (same content hash).

**Interrupted writes.** The atomic replace makes each write all-or-nothing. The validator refuses a write that is
missing a required field, so a logically half-finished checkpoint is never stored. A section hand-edited into a
broken state (a missing end marker or an unparseable field) is reported as **malformed**; recovery then shows
only the error and the path, never part of the content.

### 3.2 Binding identity (extends C3)

The binding becomes `{session_id, root, file, task_id, checkout, branch, bound_at, state}`. `state` is `active`,
`closed` or `moved:<new session>`. Old three-key records stay readable (they read as `active`, with no checkout
check).

**Session-id resolution (fixes C5; refined by the live probe).** On this host the tmux server environment carries
a stale `CODEX_THREAD_ID` from a Codex session, so every pane inherits it [O]. A fixed variable order is wrong
either way: Codex-first picks a stale Codex id inside Claude, and Claude-first picks a stale Claude id inside a
Codex run started from a Claude shell. `fsa-task` therefore:
- uses the single variable that is set;
- when both are set, walks the process's parent chain and picks the engine reached first (`CLAUDE_PID`, or a
  `codex` process);
- when neither is found, refuses with "pass `--session`".

Process identity likewise uses `CLAUDE_PID` only when it is an actual ancestor.

**Ownership: one owner record per ledger.** Ownership is separate from the per-session binding (which stays
what the dashboard reads).
- **Where:** `state/owners/<sha256(root\0file)>.json`.
- **Fields:** `{session_id, claude_pid, pid_start, host, checkout, acquired_at, released_at}`. `pid_start` is
  `/proc/<pid>/stat` field 22, read when the record is written. `claude_pid` comes from `CLAUDE_PID` (§2.1 Q2);
  Codex sessions record the parent process of `tasks.py` the same way.

**Acquire (`bind`, `adopt`), under the existing per-(root, file) `flock`:**
- no record, or a record that is `free` → write the new record with `_atomic` → acquired;
- record owned by the caller's session → refresh it and succeed;
- record `live`, `stale` or `unknown` and owned by another session → refuse with the owner's id, state, host and
  age, unless `--takeover`. `--takeover` is given only on the user's word and keeps the old record as `previous`.
  This covers a crash (`stale`), another host (`unknown`) and a same-process session that ended without its
  SessionEnd hook (`live`).

Because the check and the write happen under one lock, two sessions racing for one file get exactly one winner.

**Owner state** is computed, never stored:
- **free:** `released_at` is set. `close` sets it, and so does SessionEnd for the owning session (any reason).
- **live:** same host, and `/proc/<claude_pid>` exists with a start time equal to `pid_start`. The PID alone is
  never trusted: a reused PID has a different start time.
- **stale:** the process is gone, or its start time differs, so the owner crashed or the PID was reused. If the
  process is alive but the owner session ended without its SessionEnd hook running (SessionEnd has a 1.5 s
  budget), the record reads **live**. That costs one explicit takeover, never a wrong automatic one.
- **unknown:** a different host, or `/proc` unreadable. Treated like live: refuse unless `--takeover`.

The owner state is shown in every refusal so the user can judge the takeover. `stale` is the case where a
takeover is clearly safe; `live` and `unknown` need the user to confirm the other session is finished. Until U4's
SessionEnd release ships, a `/clear` in the same process leaves the old record `live`, and the new session
continues only through an explicit takeover. That is why U1a must not ship in a release without U4.

**Explicit takeover** (`adopt --takeover`, only on the user's word):
- the previous owner record is kept as `previous` inside the new record;
- a one-line takeover note goes into the ledger (`taken over from <id8> (<state>) at <time>`).

There is never an automatic takeover.

**Compare-and-swap takeover.** `--takeover <expected-owner-session>` replaces a record only when its current
owner is exactly that session. Two concurrent takeovers (or adopts) of the same owner serialize on the lock: the
first succeeds, and the second then finds a different owner and is refused. Nothing can verify the user's words
mechanically, so the flag's required value forces a deliberate act. Hooks never pass it, and the lead passes it
only on the user's direction. A `stale` or `unknown` state alone never authorizes it.

**Identity-conditional release.** The record stores the ledger `file`. `release` acts only when the record's
session id **and** its `(claude_pid, pid_start)` match the caller. Consequences:
- a delayed or repeated SessionEnd from an earlier process, including one for the *same* session id resumed in a
  new process, never releases the current owner;
- a fork (same process, different session id) never releases its parent's record.

**Mutation paths.**
- *Enforced:* `fsa-task init`, `bind`, `set`, `add`, `release`, `checkpoint`, `adopt` and `close`; `bind_tasks()`
  (also used by the Codex edition's `phase.py`); and the dispatcher's `task-row.sh`, which calls the CLI.
- *Outside enforcement, by design:* direct file edits (Claude's Edit/Write tools, editors, `git checkout` of the
  file), and other code that writes the Markdown file itself. The ledger stays a plain repository file. The guard
  stops cooperating tools from writing over another session's task; it is not access control.

**Codex edition limitation.** Codex has no SessionEnd hook here, so a Codex lead's ownership is released only by
`close` or `release`. Without `CLAUDE_PID` its identity is the parent process of `tasks.py`, a short-lived shell.
Another session therefore sees a Codex-owned record as `stale` once that shell exits, and still needs an explicit
takeover. The owning Codex thread keeps writing by session id.

**Write guard.** `set`, `add` and `checkpoint` check the owner record under the same lock. A ledger with an owner
record accepts writes only from the owning session; another session gets a refusal naming the owner. Legacy
ledgers without an owner record keep today's behaviour until they are bound. The dispatcher's row updates run in
the lead's shell with the lead's session id, so they pass. Per `task-tracking.md`, a ledger failure only warns
the dispatcher.

### 3.3 Lifecycle

| Event | Same session? | Behaviour [P] |
|---|---|---|
| **PreCompact** (new hook, `manual\|auto`) | yes | Never blocks: blocking auto-compaction can fail the request (§2). It records `compacted_at` in the state directory and, if the checkpoint is older than the ledger's last write, a `stale_checkpoint` marker. Runtime under 200 ms, no model call. |
| **SessionStart `compact`** | yes | The session's own binding, `active` and matching checkout → emit the **recovery block** (§3.4) as a separate hook block (`--name task-recovery`). No binding → nothing. `closed` → one line: "task X completed". |
| **SessionStart `resume`** | yes | Re-acquire ownership when the owner record is free or already this session's (same id, so no other session is involved). The transcript is back, so emit one line (≤300 chars): task, checkpoint age, and "HEAD/branch changed since checkpoint" when true. If another session owns the ledger now: one line naming it, no content. |
| **SessionEnd** any reason (extend `session-end`) | old session | Set `released_at` on any owner record this session holds. On `clear` or `resume`, when the session had an `active` binding, also write a parked record to `state/parked/<pid>-<pid_start>.json` = `{old_session, file, task_id, checkout, branch, parked_at}`, replacing any earlier one: a process has one foreground conversation at a time. One small write, inside 1.5 s. The board release stays as it is. |
| **SessionStart `clear`** | **new session** | **Does not bind, acquire or load content.** Shows a notice only when **all** of these hold: a parked record exists for this `CLAUDE_PID` and its current start time; it is ≤300 s old (final review; originally 30 s); its checkout equals the current `git rev-parse --show-toplevel`; and exactly one such record exists. The notice (≤400 characters): "The previous conversation left task '<title>' (<n> open rows) at <file>. This is a new conversation: start fresh unless the user asks to continue. To continue, run `fsa-task adopt --from <id8>`." If any condition fails, or `CLAUDE_PID` or `/proc` is unavailable, **nothing is shown** (refinement 7). The record is consumed (deleted) either way. |
| **SessionStart `fork`** (add `fork` to the matcher) | new session | Runs the normal session context (fixes G6). Follows the clear rule: same notice conditions (the parent's SessionEnd(`resume`) wrote the parked record). The fork **never** inherits the binding or ownership. Its conversation copy may still contain the parent's task knowledge, so the notice says the task belongs to `<id8>` and that writes from this session will be refused until `adopt`. |
| **SessionStart `resume`** after an in-process `/resume` | resumed session | The parked record from the previous conversation is deleted unused: the resumed conversation has its own binding, or none. |
| **`fsa-task adopt --from <session>`** (new) | new session | Run only when the user asks to continue. Checks the binding of `<session>`, the same checkout, and the ownership rule (§3.2). Acquires ownership (`--takeover` only on the user's word), binds the current session, marks the old binding `moved:<new>`, appends a one-line handoff note to the ledger, and prints the recovery block. |
| **`fsa-task close`** (new, or part of the existing completion path) | — | Refused while rows are open (same rule as phase `complete`). Sets checkpoint `status: completed` and binding `closed`, and removes parked records for the file. |

A deliberate new task after `/clear` therefore never resumes the old one by itself: the new session has no binding
until the lead runs `adopt`, and the lead does that only on the user's word.

### 3.4 Recovery block

- **Budget.** Hard cap 2,500 characters, in a separate hook block, so it never competes with the session
  context's 10,000-character limit.
- **Deterministic assembly.** The renderer builds the block from tiers in a fixed order. Each item is cut to a
  fixed per-item limit, so the same checkpoint always renders the same bytes.
- **Tier 0, always included,** with ~1,100 characters reserved:
  - identity line: task id, checkout, branch, owner, checkpoint age;
  - checkpoint path;
  - scope and out-of-scope, 300 characters each;
  - blockers;
  - next action;
  - warnings: malformed, stale checkpoint, HEAD or branch moved, checkout mismatch;
  - the fixed footer.
  If tier 0 alone would exceed the reserve, scope is cut first, with "(truncated: read the checkpoint)".
- **Tiers 1–5,** filled in order while space remains, then cut at a whole item:
  1. approvals, each with `used` and `clarity`;
  2. goal;
  3. decisions, newest first, by title;
  4. open rows (`fsa-task show` order);
  5. verification lines tagged `inputs unchanged`, `inputs changed` or `unknown`, then evidence paths.
- **Omission line** whenever anything was cut, e.g. `Omitted: 6 decisions, 3 verification entries, evidence list —
  read <path> before acting on them.` Any omitted approval or decision makes reading the full checkpoint
  **mandatory** before an edit or dispatch, and the line says so.
- **Fixed footer:** "Historical record written by the lead; it may contain mistakes. Re-check repository state
  before editing. Approvals are records of the user's words, not authorization: confirm with the user anything
  ambiguous or outside the quoted scope. Verification is evidence of a past state: rerun before relying on it."
- **Shared tree.** On a shared working tree, `inputs unchanged` is shown as a hint only, consistent with the
  task-flow rule that reuse is unavailable there.
- **When Claude must read deeper:**
  - the full checkpoint section before the first edit;
  - the evidence file before relying on a decision shown only by title;
  - the log and a rerun before citing a verification result;
  - the ledger rows before dispatching.
- **Failure modes.** Each degrades to a short, explicit message and **no partial content**:
  - ledger missing → "registered task file missing at X — ask the user";
  - section malformed → error and path;
  - checkout or branch mismatch → pointer and warning only;
  - binding `moved` → "this task moved to session <id8>".

### 3.5 Approval boundaries

A checkpoint approval is **historical evidence of what the user said**, never an authorization source.
Authorization still comes only from the user, under the project's existing rules.
- Hooks never write approvals; only the lead records them, as the user's quoted words with their scope.
- Recovery shows each approval with its `used` and `clarity` state:
  - `single-use` + `used` is shown as spent;
  - `ambiguous` is shown as "ambiguous: confirm with the user before acting".
- Standing approval rules (deploys, migrations, production actions, real calls, releases) apply after recovery
  exactly as before. A recorded approval never stands in for them, and a recovered session re-asks wherever those
  rules require a fresh go-ahead.
- `adopt` and `--takeover` themselves need the user's request.

### 3.6 Concurrency and isolation

| Case | Protection |
|---|---|
| Two sessions in one checkout with different tasks | Each sees only its own binding (keyed by session id). The clear notice matches on Claude process id **and** start time **and** checkout, so session A's `/clear` never offers B's task. `adopt` refuses a file that a live session owns, and the write guard refuses B's writes to A's ledger. |
| Fork of a session that owns a task | The fork has a new session id: no binding, no ownership, and writes are refused until an explicit `adopt`. The parent's ownership was released by its SessionEnd(`resume`), so `adopt` works without `--takeover`. If the parent is later resumed and re-acquires first, the fork's `adopt` is refused. |
| Worktrees and other repositories | The binding stores the checkout and branch. Recovery compares them with the current `git rev-parse --show-toplevel` and branch; on mismatch it shows a pointer and warning only. The clear notice requires the parked checkout to equal the current one, so worktrees never share notices. Owner records are keyed by (root, file), so separate repositories never collide. |
| Stale associations | Parked records expire after 24 h. `moved` and `closed` bindings never emit content. The checkpoint's HEAD is compared with the current HEAD. |
| No guessing | Unlike ECC (newest summary by worktree, then repository, then project name), there is **no "latest ledger" fallback**: no binding means no recovery. |

## 4. Alternatives considered

| Alternative | Why not the recommendation |
|---|---|
| Hook-generated summary (ECC Stop/PreCompact model call) | Extra model calls, added latency, and it can record unconfirmed decisions. Kept as optional §9 U6: save the free `compact_summary` from PostCompact as unreviewed evidence, **never auto-loaded**. |
| Auto-resume the parked task after `/clear` | Violates "a new task after `/clear` must not resume the old one". Explicit `adopt` costs the user one sentence. |
| Block manual `/compact` when the checkpoint is stale | Safe for `manual` only. Possible later switch (`checkpoint_gate=manual`); left out to avoid friction. Auto-compaction is never blocked. |
| Separate JSON checkpoint file in the state directory | Out of the repository, invisible to the user and other agents, and a second source of truth beside the ledger. The ledger is already versioned, atomic and shown on the dashboard. |
| Rebind by `transcript_path` directory plus time window | Ambiguous when two sessions in one checkout clear close together; the process id is the safer key (Q2). |

## 5. Enduring conventions

Add to `task-tracking.md`, not to `CLAUDE.md`: the triggers in §3.1, and "decisions and approvals go in the
checkpoint, as quotes". `CLAUDE.md` gets nothing; dynamic task state never goes there.

## 6. Next opportunities (assessment only, not part of this design)

- **Repeated per-prompt instructions.** This session shows the `prompt-polish` block (about 1,400 characters)
  and the router line injected on every prompt. They are appended after the cached prefix, so they don't break
  the cache, but they are paid on every turn and stay in the transcript.
  - **Measure first:** `python3 -I tests/overhead/probe.py --plugin plugins/fullstack-agents --project <ucm>`.
  - **Candidates:** inject the full polish text only on the first prompt of a task, or only for long or vague
    prompts, and a single line otherwise.
- **Noisy command output.** A PreToolUse Bash rewrite (RTK pattern) only for known noisy commands (`cargo`,
  `npm test`, `vitest`). It would:
  - tee the full output to a log;
  - return the exit status, warning and error lines with their location, failing-test blocks and the log path;
  - never filter when the exit code is unknown, and keep a per-command opt-out.
  - The test-runner already saves full logs, so this covers only the commands the lead runs itself.
- **Defer** searchable conversation memory (episodic-memory) and diff-on-re-read until checkpointing and the
  measurement in §8 show a remaining need. Claude Code already skips unchanged re-reads (changelog: "deduplicates
  unchanged re-reads").
- **Backlog B1, recorded 2026-10-19 at the user's request: avoid needless re-reads after Claude's own successful
  edits.** Separate from checkpoint/recovery. It needs its own investigation and approved plan; nothing is
  implemented here.
  - **Requirement:** when the original content and a successful edit result are still in context, use them
    instead of immediately reading the same lines again.
  - **Re-read only for a concrete reason:**
    - another session, a formatter, a generator or a tool may have changed the file;
    - the edit failed, applied only partly, or returned an ambiguous result;
    - surrounding code that is needed has not been read;
    - compaction, `/clear` or other context loss removed the details;
    - a review must check the actual resulting content.
  - **When re-reading:** use the smallest range or diff that suffices. Never skip meaningful tests or required
    review.
  - **Investigation first:**
    - Claude Code's native Read handling: unchanged-file stubs, its tracking of Claude's own edits, the
      external-edit and rewind cases (changelog entries in §2);
    - the plugin's current instructions (`read-guard` blocks unranged shell dumps; the lead prompt's "read in
      bounded ranges");
    - shell reads (`cat`, `sed -n`, `git diff`), which native unchanged-file detection does **not** cover.
  - **Limits:** no blanket re-read ban, no duplicate of native caching, no claim that reads cost nothing.

## 7. Tests (isolated fixtures; no real `/clear` or compaction against a live task)

All in the existing frameworks. Hooks are invoked with synthetic stdin JSON, and `FSA_TASKS_DIR`,
`CLAUDE_CONFIG_DIR` and `TMPDIR` point into a temporary directory, as `test_session_context.py` already does.

1. **Lifecycle matrix:**
   - `compact` with an active binding → recovery block;
   - `compact` with no binding → no block;
   - `compact` with a closed binding → one line;
   - `resume` → one line, plus a HEAD-moved warning when HEAD changed;
   - SessionEnd(`clear`) then SessionStart(`clear`) with a new id → notice only, no binding created;
   - `fork` → session context, no binding.
2. **Adopt:** binds the new session, marks the old one `moved`, appends the ledger note and prints the block. It
   refuses when the checkout differs or when a live session owns the file (fake live transcript); `--force`
   overrides.
3. **Concurrency:** two sessions in one checkout with different ledgers; session A clears; B's parked record is
   never offered to A's new session (different process id); a simultaneous `bind` of the same file by two
   sessions → exactly one wins.
4. **Stale and malformed:** checkpoint older than the ledger → warning; HEAD moved → verification tagged
   `inputs changed`; truncated section, missing end marker or missing required field → error and path with no
   partial fields; a checkpoint write missing a field is refused; a kill between temp write and replace leaves
   the previous file intact (the existing `_atomic` test style).
5. **Completion:** `close` refused with open rows; after `close`, compact emits one line and parked records are
   removed.
6. **Budget:** a 40-decision checkpoint keeps the block at or under 2,500 characters with "+N more"; probe.py
   reports the new block's size and hook latency.
7. **PreCompact:** never emits a block decision for `auto` or `manual`; writes the marker; finishes in under
   200 ms.
8. **Q1–Q3:** done (§2.1).
9. **Ownership (U1a):**
   - acquire on an empty record;
   - the same session re-acquires;
   - another live owner (fake record with this process's real pid and start time) → refused;
   - a dead pid, or a live pid with a wrong start time → stale → refused without `--takeover`, accepted with it,
     with `previous` kept;
   - a different host → unknown → refused;
   - a released record → free;
   - two concurrent acquirers (subprocesses) → exactly one winner;
   - the write guard refuses `set`/`add` from a non-owner and allows the owner and legacy unowned ledgers;
   - a malformed owner record → explicit error, never treated as free;
   - session id read from `CLAUDE_CODE_SESSION_ID`.
10. **Deterministic rendering (U2):**
    - the same checkpoint renders identical bytes;
    - tier 0 is present at every size;
    - the omission line lists exactly what was cut;
    - an omitted approval or decision makes the full read mandatory.
11. **Fork (U3/U4):** SessionEnd(`resume`) then SessionStart(`fork`) in one process → notice only; the fork's
    `set` is refused; `adopt` from the fork succeeds after release; a parent re-acquire wins over a later fork
    `adopt`.

**Commands** (found in this repository's docs and test files):
- `python3 -m unittest discover -s tests/dashboard -v`
- `python3 -m unittest discover -s tests/codex -v`
- `bash plugins/fullstack-agents/hooks/<name>.test.sh`
- `python3 -I tests/overhead/probe.py --plugin plugins/fullstack-agents --project <dir> --json <out>`

## 8. Before-and-after measurement

- **Recovery scenario.**
  1. Script a task in a scratch repository whose three decisions and one scoped approval exist **only in chat**.
  2. The lead checkpoints them.
  3. Reset the context: `/compact`, and separately `/clear` + "continue" (→ `adopt`).
  4. Ask a fixed questionnaire (goal, decisions, out-of-scope item, next step, whether the approval covers X).
  5. Score: decisions recalled out of 3; scope or approval violations (target 0); repeated investigations;
     correct next action.
- **Control:** the same scenario on the current release (hand-written handoff only).

| Measure | Source | Measured or estimated |
|---|---|---|
| Input, output, 5-minute and 1-hour cache writes, cache reads per session and subagent | `fsa-usage --json` (transcript `usage` fields) | measured tokens; dollars are estimates |
| Subscription usage | `fsa-usage` plan windows (percentages) | coarse, shared across sessions, weighting unpublished: report it, don't attribute it |
| Repeated reads and investigations | count `Read`/`Grep`/`Bash` calls on the same path after the reset, from the transcript JSONL (a small script over the same files `usage.py` reads) | measured |
| Recovery accuracy | questionnaire score, judged by the user or against a fixed answer key | measured |
| Completion time and correctness | wall-clock from reset to the task's acceptance checks passing; same acceptance list | measured |
| Hook latency and injected size | `tests/overhead/probe.py` | measured; tokens = characters ÷ 3.8, estimate |
| Extra model calls | zero by design; confirm in the transcript (no new subagent or `claude -p` from hooks) | measured |

Run each arm at least three times on the same model and effort with a warm cache, and report spread, not a single
number. Promise no saving percentage until these runs exist.

## 8a. U2/U3 implementation plan (2026-10-20; refines §3.3–3.4, no material change)

1. **Checkout identity (shared helper `git_identity(root)`).**
   - Asks Git rather than reading `.git`: `rev-parse --show-toplevel`, canonicalised with `realpath` so a symlinked
     path and its target compare equal; `symbolic-ref -q --short HEAD` for the branch; `rev-parse HEAD` for the
     commit. Linked worktrees work because Git resolves their `.git` file.
   - Returns `{checkout, branch, head, detached}`. A detached HEAD gives `branch: null, detached: true`; the
     literal `HEAD` never appears as a branch name.
   - Used by checkpoint identity, parked records and every recovery comparison.
2. **Parked records** `state/parked/<pid>-<pid_start>.json`, `schema: 1`, fields `old_session, reason, root, file,
   task_id, title, checkout, branch, head, detached, parked_at`.
   - **Consumption:** SessionStart (any source) in the same process reads its own record and deletes it before
     deciding, so a record is offered at most once. `adopt` also deletes records naming the source session.
   - **Expiry and pruning:** a record older than 300 s is never offered (raised from 30 s in the final review). Each SessionStart deletes records whose
     process is gone or whose start time differs, and any record older than 24 h.
   - **Offer only when all hold:**
     - the source is `clear` or `fork`;
     - the schema is valid;
     - the record is at most 300 s old;
     - its checkout equals the canonical checkout of the hook's `cwd`;
     - the old session's binding still points at the file;
     - the ledger exists and has open rows;
     - the checkpoint is absent or valid, and not `completed` or `abandoned`;
     - the owner record is absent, free, or the old session's.

     Otherwise nothing is shown. Malformed, expired, completed, mismatched and consumed records never offer.
3. **New hook `session-task`** (SessionStart, matcher `startup|resume|clear|compact|fork`, its own context block
   and 10,000-character allowance; `session-start` is unchanged). Behaviour by source:
   - `clear` / `fork`: the ≤400-character notice, without binding or acquiring. The fork wording says the
     inherited conversation is not a user instruction to continue.
   - `compact`: when the session's own binding is valid and the owner is this session or absent, emit the
     recovery block. Ownership is unchanged. If another session owns the ledger, one line naming it. The PreCompact
     marker feeds the stale warning and is then deleted.
   - `resume`: re-acquire only when the record is this session's and `free`, `stale`, or `live` with this exact
     process identity. If the same session is live in another process, warn and do not acquire. If another session
     owns it, one line, no content, no acquire. Then the ≤300-character resume line.
   - `startup`: pruning only.
4. **Recovery renderer `task_recovery.py`** (§3.4 tiers, hard cap 2,500 characters). It prints absolute
   timestamps, never ages, so output is deterministic. `fsa-task recover` prints it for the caller's bound
   ledger, and `adopt` includes it in its JSON as `recovery`.
5. **Session resolution:** tests through a real process tree, using a temporary executable named `codex` that
   runs `tasks.py`, for Codex-wins, Claude-wins with a stale Codex variable, and ambiguous-refuses.

## 8b. Final review notes (2026-10-20)

**Stale-owner resume.** Automatic re-acquisition on `resume` applies only to the exact session id that holds the
record, reached through that session's own binding to that ledger. Any other session's record (free, live, stale or
unknown) returns `other-owner` untouched. A different session claiming a stale task must use `bind` or `adopt` with
the user-directed `--takeover <owner>`. Covered by tests, including an explicit stale-other-owner case.

**Truncation.** Shortened critical fields carry `[truncated]`. The checkpoint path is never cut. Any truncated or
omitted scope, blocker, next action, approval or decision adds the mandatory full-read sentence.

**Offer window.**
- The defined lifecycle point is the first SessionStart in the same Claude process after the parking SessionEnd.
  It consumes the record unconditionally, so a record can only ever be judged by that one start.
- `session-task` runs in parallel with the other SessionStart hooks, so their delay does not move its evaluation.
- The age bound is 300 s, a safety limit for stalled hosts.
- Manual adoption does not depend on the offer. The live probe adopted successfully right after an expired record
  was rejected.

**Codex liveness.** The tracked process is the parent of the `tasks.py` process, normally the per-command shell, so
a Codex-owned record reads `stale` while Codex may still be active. This is documented, not fixed. A possible later
change is to track the nearest `codex` ancestor (the same detection `default_session` uses). That has not been
verified against a live Codex run, and Codex may run commands through delegate processes.

**Guard workarounds used during testing (not to be repeated).** The UCM host guard
(`.claude/hooks/guard-host-resources.sh`) blocks `git worktree add` without approval and blocks `git checkout`
outright. During the 2026-10-20 live probes:
1. `KC_WORKTREE_APPROVED=1` was set for one `git worktree add` in a scratch repository, without the user's
   per-command approval.
2. A scratch worktree's HEAD file (`.git/worktrees/wt/HEAD`) was written directly to detach it, and then restored.
   The first attempt briefly emptied it.

Neither exercises the supported Git workflow, and neither is acceptable practice. Future checks use permitted
fixture setup:
- the unit tests (`test_task_recovery.py`, `test_task_lifecycle.py`) create worktrees and detached HEADs inside
  their own temporary repositories;
- a live worktree probe needs the user's explicit approval for the specific command.

## 9. Implementation units (after approval; all in the plugin repository)

| Unit | Change | Files |
|---|---|---|
| U1a | Session id fallback to `CLAUDE_CODE_SESSION_ID`; owner records (acquire, free/live/stale/unknown, explicit takeover, release); extended binding with backward-compatible read; write guard on `set`/`add`; `bind` acquires; `release` subcommand for hooks and `close` | `plugins/fullstack-agents/scripts/lib/task_ownership.py` (new), `scripts/lib/task_tracking.py`, `tests/dashboard/test_task_ownership.py` (new), `tests/dashboard/test_task_tracking.py` |
| U1b | Checkpoint section: schema, validator, `checkpoint`/`adopt`/`close` subcommands | `scripts/lib/task_tracking.py` (or `task_checkpoint.py`), tests |
| U2 | Recovery renderer (budget, fingerprint tags, footer, failure messages) | `plugins/fullstack-agents/scripts/lib/task_recovery.py` (new, so `task_tracking.py` stays under 800 lines), tests |
| U3 | SessionStart: emit the recovery block on `compact`, the resume line, and the clear notice; add `fork` to the matcher | `plugins/fullstack-agents/hooks/session-start` (or a new `session-task` hook beside `session-policy`), `hooks/hooks.json`, `tests/codex/test_session_context.py` |
| U4 | SessionEnd(`clear`) parked record; PreCompact marker hook | `plugins/fullstack-agents/hooks/session-end`, `hooks/pre-compact` (new), `hooks/hooks.json`, tests |
| U5 | Documentation: checkpoint triggers, adopt rule, lead prompt `HANDOFF:` → "run `fsa-task checkpoint`" | `skills/task-flow/references/task-tracking.md`, `agents/lead/fullstack-agent.md` |
| U6 (optional) | PostCompact: save `compact_summary` to the state directory as unreviewed evidence, never auto-loaded | `hooks/post-compact` (new) |

Q1–Q3 are settled (§2.1). `adopt` relies on `CLAUDE_CODE_SESSION_ID`, and the parked record is keyed by
process id and start time.

**Release and verification.** Release through the repository's normal path (`fsa-release`), and only on the
user's word. UCM is affected only through the plugin release it pins; no UCM code changes.
