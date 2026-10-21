# fullstack-agents workflow overhead review (focus: tests, clippy, checks)

Status: review of 2026-10-20. Adopted in 3.67.0: T1 (plugin side; the UCM binding text in §8 is a proposal, not applied), T3, T4, T9, W1. Not adopted: the other recommendations, which need their own scope and approval. Owner: the requesting user. Written 2026-10-20 by session
`927f3bb3`. Source state: plugin `main` at `075e714` (3.66.0) plus the uncommitted L1′/L2 work in the main checkout; UCM
bindings at `omnichannel-dev` HEAD. Retire when the recommendations below are accepted, rejected or superseded.

Labels: **[M]** measured from existing transcripts/run records; **[S]** read in source; **[E]** estimate; **[U]** unavailable.

## 1. Measurements

UCM lead sessions with activity since 2026-10-14 (20 sessions, `~/.claude/projects/-home-adel-workspace-ucm/*.jsonl`),
foreground verification commands only (tool-use → tool-result time) **[M]**:

| Command class | Runs | Hours | Avg s |
|---|---|---|---|
| `scripts/test-backend.sh` | 244 | 8.5 | 125 |
| frontend (vitest / tsc / eslint) | 268 | 5.3 (≈0.8 without two ~8,000 s outliers in session `7e8e1456`) | 71 |
| clippy | 183 | 2.7 | 54 |
| other cargo build/test | 59 | 0.5 | 28 |
| `cargo check` (lead) | 21 | 0.2 | 32 |

- Identical verification command rerun with no edit or dispatch in between: **12** in total (8 of them `test-backend.sh`)
  **[M]**. Redundant reruns are not the main cost; volume and ordering are.
- Runs that hit the 600 s Bash cap (output lost, run repeated): **7 `test-backend.sh`, 3 clippy** **[M]**.
- Clippy runs whose output contained errors: **21 of 215** **[M]**. Each of those happens after the implementer finished, so a
  lint failure costs a repair round. Ledger examples: `tasks/chatbot-standalone.md` V4 "chatbot_limits map_or fixed by
  Codex (s5b-r3)", S4b "clippy fix applied" **[M]**.
- Implementer dispatches 2026-10-19/20 (all repositories): 27 briefs, 16 of them repair/fix briefs **[M]**. This session:
  11 dispatches, of which 3 repaired 17 real defects found by the lead diff audit, 2 fixed tests broken by an intended
  default change (preventable by naming those tests in the first brief), 1 added a test a mutation check exposed, 1 was a
  requested repair **[M]**.
- This session's own verification: 6 full plugin-suite runs (≈100 s each, ≈10 min of ≈2 h wall) and 2 mutation rounds
  (seconds) **[M]**. Implementer-side check time lives in run logs, not lead transcripts, and was not summed **[U]**.
  Token cost per stage **[U]** (only lead totals exist: $11.32 through L2).
- Earlier baseline (`FULLSTACK_AGENTS_WORKFLOW_INVESTIGATION.md` §1): builds/tests were 47–53 % of active lead time in two
  sessions **[M, earlier]**.

## 2. How checks run today (Rust backend deliverable, UCM)

| Step | Who | Command | Purpose | Duplicate of |
|---|---|---|---|---|
| 1 | implementer | `SQLX_OFFLINE=true agent-cargo.sh backend check -p <crates> --tests` (UCM binding) | type errors before return | — |
| 2 | lead | the same check across every touched crate after each batch (UCM binding) | catch other units' breakage | step 1 for single-unit batches |
| 3 | lead | `agent-cargo.sh backend clippy -p <crates> -- -D warnings` | lint gate | type-check part of step 2 (clippy runs the full check) |
| 4 | lead / test-runner | `test-backend.sh -p <crate> --test <t>…` affected targets | behaviour | — |
| 5 | lead / test-runner | one whole-crate `test-backend.sh` per deliverable | regressions | — |
| on lint fail | implementer | repair brief | — | a full dispatch round for a lint fix |

Contradictions **[S]**:
- `rust-quality-gates` prescribes `cargo fmt --all --check`, workspace clippy, `cargo test --workspace`, `cargo audit` and an
  80 % coverage gate "after every Rust change", and says hooks run "fmt+clippy at stop". In UCM the tree is not
  rustfmt-clean (`FSA_SKIP_RUSTFMT=1`), `agent-cargo.sh … test` hits the production `DATABASE_URL`, no hook runs clippy
  (`hooks/post-edit-validate:51-54` only rustfmt-on-edit, disabled in UCM), and coverage is never measured. The project
  binding wins by precedence, but the skill invites the most expensive and, in UCM, unsafe chain.
- The task-flow skill says the implementer "does not run test suites"; plugin-repo briefs (this session) let it run focused
  unit tests, which was useful there (seconds) and is harmless; UCM DB tests must stay lead-side (DB lock, prod URL risk).

## 3. Recommendations — tests and checks

| # | Class | Recommendation | Reason / evidence | Risk | Protection kept | Benefit |
|---|---|---|---|---|---|---|
| T1 | **merge** | Implementer BUILD becomes `SQLX_OFFLINE=true agent-cargo.sh backend clippy -p <crates> --all-targets -- -D warnings`; the lead reruns that one command once per integrated batch; drop the separate `check` step. | clippy performs the full type-check; 21/215 clippy runs failed after the implementer had returned, each costing a repair round (s5b-r3) | implementer build ~20 s longer **[E]** | same compile + lint, earlier | one compile pass and most lint repair rounds removed per batch **[E]** |
| T2 | **keep** | Affected targets first, one whole-crate run per deliverable, at the end; reruns only for crates whose inputs changed. | identical reruns already rare (12) **[M]** | — | — | — |
| T3 | **add** | Split any `test-backend.sh` invocation expected to exceed ~8 min into target groups in one command each, or hand it to `test-runner` with a target list. | 7 runs hit the 600 s cap and lost output **[M]** | more invocations | same coverage | no lost runs |
| T4 | **simplify** | `rust-quality-gates`: per-change chain = rustfmt on changed files, clippy on touched crates with `--all-targets`, tests through the project runner; `cargo audit`, workspace clippy and any coverage figure move to release-only; delete the "hooks run clippy at stop" claim. | contradicts UCM bindings; the claimed hook does not exist **[S]** | none known | project bindings unchanged | no expensive/unsafe chain suggested to the lead |
| T5 | **keep** | Implementers never run DB tests in UCM; in repos whose unit suite runs in < 1 min (this plugin) the brief may include it. | DB lock + prod URL **[S]**; plugin suites 15 s / 80 s **[M]** | — | — | — |
| T6 | **simplify** | Plugin repo: during repair loops run only the touched test modules; the full dashboard + codex suites once per integration boundary. | 6 full runs this session where 2 would have sufficed after the last code change **[M]** | a cross-module break found later in the same boundary | final full run | ~5 min per task here **[E]** (small) |
| T7 | **keep, bounded** | Mutation checks only for enforcement branches of gates (≤ 10 lines per deliverable), on a scratch copy. | caught one real coverage gap in L2 (M4) in seconds **[M]** | — | — | — |
| T8 | **simplify** | New tests assert outcomes (refused, status/bytes unchanged) and only user-facing key phrases, not full messages. | `test_task_evidence.py` 744 lines for a 799-line module; many `assertIn(<message>)` **[S]** | slightly weaker message checks | outcome assertions | fewer brittle failures on wording changes |
| T9 | **add (brief rule)** | When a brief changes a default or shared behaviour, its ALLOWED_PATHS include the tests that pin the old behaviour (grep them first). | 2 of 11 dispatches this session were such fixture fixes **[M]** | larger first brief | — | fewer one-line repair dispatches |

Detection is unchanged: a failed implementation still fails at the implementer's clippy (compile/lint), at the lead's
single rerun (cross-unit breakage), and at affected/whole-crate tests (behaviour).

## 4. Recommendations — workflow (brief)

| # | Class | Recommendation | Reason / evidence | Protection kept |
|---|---|---|---|---|
| W1 | **merge** (before the single release) | The brief's `BUILD:` and numbered `ACCEPTANCE:` commands become the deliverable's L2 checks automatically when the brief has `TASK:`; scope defaults to the brief's ALLOWED_PATHS plus a `DEPENDS:` line; `accept` gets a one-line shorthand. Results recorded by `check run` when the lead (or test-runner) executes them. | L2 currently needs a hand-written JSON spec per deliverable; no lead instruction uses it yet, so as shipped it would add per-task authoring cost and duplicate the brief's acceptance list **[S]** | the gate, freshness and reopen rules unchanged |
| W2 | **remove** | Manual `team-board steps` when a ledger exists; manual phase declarations except `complete`/`review`. | ledger rows, board steps, board phases and checkpoint `done[]` track the same progress **[S]** | ledger + derived dashboard phase |
| W3 | **remove** | The checkpoint's porcelain `verification[]` fingerprint; checkpoint verification entries cite L2 results instead. | two fingerprint systems; the porcelain one misses re-edits of dirty files **[S]** | L2 content fingerprints |
| W4 | **simplify** | Prompt-router output is advisory below 0.8 confidence (no "mandatory"/"NOT LOADED" wording); the edit-time skill gate stays. | this session: 4 of 9 prompts routed to unrelated lanes (debug, nextjs, rust-correctness) **[M]** | skill-gate on edits |
| W5 | **keep** | Lead diff audit per deliverable. | found 17 real defects incl. a gate bypass in 2 audits **[M]** | — |
| W6 | **simplify** | One review boundary per deliverable: lead audit of the integrated diff + required checks; `diff-reviewer` lenses only for carve-outs/security; no re-audit of unchanged code after a repair (review only the repair diff). | — | — |
| W7 | **keep** | Fingerprints (content, scoped) — they are what stops "pass, then edit, then done". Baseline attribution: **keep code, exception-only**; no lead instruction requires it. | used once per ~10 ledgers (V3, B4) **[M]** | — |

L3–L5: **reduce L3** to typed blockers + one derived state + stop-guard rule + `phase complete` refusal + push → review;
drop row-chain root analysis and the separate `blocked` cycle state (rows list their own blockers). **Defer L4** (a
`## Backlog` section is an instruction, not a command). **Reduce L5** to recovery listing open blockers/unmet checks and
the instruction rewrite.

## 5. Proportional workflows and minimal check matrix

| Task | Ledger | Checks | Review |
|---|---|---|---|
| Docs / UI text | none (light path) | doc checker or `tsc`+`eslint` on touched files | lead reads diff |
| Normal feature / bug fix | v2, 1–3 deliverables, checks from brief | implementer clippy/tsc; lead: one rerun, affected tests, one full crate/package run | lead audit once per deliverable |
| High-risk (telephony, DB, security, concurrency) | v2 + scoped dependencies | as normal + migration/fixture tests, `diff-reviewer` lens, drained reload checks per UCM | lead audit + one lens |
| Read-only investigation | none | none | answer cites sources |

| Area | Per batch (fast) | Per deliverable | Release-only |
|---|---|---|---|
| Rust backend | clippy `--all-targets -D warnings` on touched crates | affected `test-backend.sh` targets, then one whole-crate run | workspace clippy, `cargo audit`, sqlx prepare check |
| Frontend | `tsc --noEmit`, `eslint <paths>` | `vitest run <paths>`; visual check when UI changed | `next build` |
| Plugin (Python/shell) | touched test modules | full dashboard + codex suites once | bundle render, `fsa-release verify`, live probes |
| Docs | `check-architecture-docs.py --self-test`, `git diff --check` | — | — |

## 6. Walkthrough: Rust bug fix, one unit, implementer leaves a clippy `map_or` warning

| Current | Proposed |
|---|---|
| implementer `check` passes → returns | implementer `clippy --all-targets -D warnings` fails → fixes `map_or` in the same run → returns |
| lead `check` (pass) | — |
| lead `clippy` fails → repair brief → dispatch → implementer `check` → lead `check` → lead `clippy` | lead `clippy` (pass) |
| affected tests, whole crate | affected tests, whole crate |
| **2 dispatches, 3 compiles, 2 clippy runs** | **1 dispatch, 1 implementer clippy, 1 lead clippy** |

A logic bug is still caught by the affected test target in both flows.

## 7. Limits of this evidence

Durations include queueing behind the DB lock and other sessions' builds; implementer-side check time and per-stage token
cost were not measured; the two frontend outliers look like blocked commands rather than slow checks; the "repair brief"
count uses brief-name patterns (`-r<n>`, `repair`, `fix`). Savings in §3–§6 are estimates, not measurements.

## 8. Proposed UCM binding text for T1 (not applied; UCM edits are out of scope)

Replace in UCM `CLAUDE.md` "Task flow" bindings when the user authorises a UCM change:

| Binding | Proposed value |
|---|---|
| Implementer BUILD | Backend: `SQLX_OFFLINE=true scripts/agent-cargo.sh backend clippy -p <crates> --all-targets -- -D warnings` (no `sg`, no Docker); frontend: `npx tsc --noEmit && npx eslint <paths>`. The lead runs the same backend command once on the integrated state of the deliverable (all units landed), before any test run, not after every batch. Extra configurations clippy does not exercise (none known today) get their own `check` line here |
| Verification scope | unchanged, plus: a `test-backend.sh` run expected to exceed ~8 min is split into target groups, each its own `fsa-task check` and log, run sequentially |

`AGENTS.md` "Commands" keeps `SQLX_OFFLINE=true scripts/agent-cargo.sh backend check -p <crate> --tests` only as the
fallback for configurations clippy does not cover.
