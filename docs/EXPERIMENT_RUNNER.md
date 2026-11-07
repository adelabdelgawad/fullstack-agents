# FSA workflow comparison runner

Status: experimental, CLI only, outside the installed plugin (`tests/experiment/`). It never edits, releases or promotes
a workflow. Owner: the requesting user. Ledger: `docs/tasks/experiment-runner.md`.

Real smoke run (2026-10-28, fixture, `claude-sonnet-5`, CLI 2.1.311): `smoke-1` tie, both accepted; A $0.24 / 35 s, B
$1.03 / 280 s over five sessions (its candidate edit was dropped at compose, so B's final run is a repeat attempt).
Preflight: auth ok, single pinned plugin, hooks from the snapshot, subagents included in the parent's CLI total, resume
totals cumulative; personal-instruction exclusion unverified (the debug log names no instruction files).

It runs one coding task twice from the same commit and task text:

- **Arm A**: the pinned FSA workflow (a read-only snapshot of a plugin directory, normally the installed cache).
- **Arm B**: a bounded loop adapted from [Harness²](https://github.com/google-research/harness2): a base run, then per
  round *propose* (an improver edits a copy of the workflow), *probe* (a run with the candidate), *compose* (an
  improver keeps only the evidence-supported edits, or keeps the base), then one final run with the composed workflow.

Then it evaluates both final diffs with the same evaluation-owned checks and writes `results.json` and `REPORT.md`.

## What is borrowed and what is ours

| Upstream Harness² (`core/recursion.py`, `prompts.py`, `library.py`) | This runner |
|---|---|
| Harness = file tree; proposer returns an edited tree | Workflow = plugin tree; every candidate is frozen with a manifest and `changes.diff` |
| INV (process) and DOM (domain) proposers | Process edits only, in `skills/**`, `agents/*.md`, `scripts/lib/roles/*.md`, ≤ 200 changed lines |
| Probing = rerunning the same task with a candidate | Same task; probe diffs are discarded; B's deliverable is `b-final` only |
| Compose: "keeping the base unchanged is a valid outcome" | Same; an unchanged final workflow is labelled a repeat attempt, never an improvement |
| No rubric or answer key during refinement | Improvers see trajectories (tool calls, states, file names, no diff content), never the checks |
| Invalid proposal: one retry, then fall back | Same; also a task-identifier scan (heuristic) |
| Lessons need cue, lesson, evidence | `arms/B/lessons.json`, scoped to the experiment |
| Executors: OpenCode, Codex | Claude Code headless (`claude -p --plugin-dir <tree> --agent fullstack-agents:fullstack-agent`) |

## One-time setup: a dedicated token

Each session gets its own `CLAUDE_CONFIG_DIR`, so it needs a token rather than your login's refresh credentials:

```bash
claude setup-token
install -m 600 /dev/null ~/.config/fullstack-agents/experiment-oauth-token
$EDITOR ~/.config/fullstack-agents/experiment-oauth-token   # the token only
```

The runner passes it as `CLAUDE_CODE_OAUTH_TOKEN` to session processes only and records `[set]`, never the value.

## Supplying a real task

1. Commit the starting state in the target repository; note the commit.
2. Write `TASK.md`: the requirement and its acceptance criteria as the agent should see them.
3. Write the evaluation material **outside** the experiment directory and, for historical tasks, off this host until
   evaluation (agents run as your user and could read it):

   ```json
   {"overlay": "overlay",
    "acceptance": [{"id": "AC1", "command": "python3 -m unittest tests_eval.test_feature", "timeout": 300}],
    "regression": [{"id": "R1", "command": "python3 -m unittest discover -s tests", "timeout": 900}],
    "env": ["NAME_OF_A_NON_SECRET_TEST_VARIABLE"]}
   ```

   `overlay/` files are copied over each evaluated tree, so an agent cannot replace them. Optional per-check keys:
   `cwd`, `skip` (a reason; recorded as `skipped`). Commit to the checks before running: `checks-hash DIR`.
4. Use a test environment. Arms start from an allowlisted environment (`--env-allow` adds names); never allow
   production credentials. A clone isolates files, not databases, services or network.
5. Each session's HOME is a fresh directory, so toolchains found through the real HOME (`~/.cargo`, `~/.rustup`, nvm,
   git identity) are missing. Export their locations (`CARGO_HOME`, `RUSTUP_HOME`, `GIT_AUTHOR_NAME`, …) and pass the
   names through `--env-allow` and the checks' `env` list; a shared cache such as the cargo registry is then an
   isolation difference to note. A report whose source commit passes no regression check flags the evaluation
   environment as suspect.

```bash
X=tests/experiment/fsa_experiment.py
python3 $X init --source ~/workspace/proj --commit <sha> --task TASK.md --model claude-opus-5-5 \
  --workflow ~/.claude-anthropic/plugins/cache/fullstack-agents/fullstack-agents/3.68.0 \
  --usd-a 10 --usd-b 30 --wall-a 3600 --wall-b 10800 --session-s 3600 --rounds 1 \
  --checks-sha256 "$(python3 $X checks-hash /path/to/checks)"
python3 $X preflight <id>                     # 4 cheap calls; records auth, loading and cost semantics
python3 $X run <id>                           # A then B (order recorded)
python3 $X resume <id> --arm A --stage a-final --message "…"   # only for a stage in needs_human
python3 $X evaluate <id> --checks /path/to/checks
python3 $X report <id>
```

Results live in `~/.local/share/fullstack-agents/experiments/<id>/` (`FSA_EXPERIMENTS_DIR` overrides): every session's
clone, transcripts, process ledger, debug log and captured patch stay there for review.

## Reading the report

- **Acceptance** is absolute: every acceptance check must pass on the final implementation. Failing on the source
  commit is expected for an unimplemented feature and never excuses a failure.
- **Regressions** are relative to the source commit: `new_regression` (passed before, fails now), `existing_failure`,
  `fixed`, `unknown` (either side not executed). Statuses `pass`, `fail`, `timeout`, `unavailable`, `skipped` and
  `unexecuted` stay distinct; anything but `pass` on acceptance means *not accepted*.
- **Outcome** is `A/B better on acceptance for this task`, `tie`, `inconclusive` or `unevaluated`. It never comes from
  self-review or agent-written tests. One task is a case study, not evidence of general improvement.
- **Practical comparison**: B's totals include every probe, proposal, retry and composition; `overhead_before_final`
  shows what B spent before its final run.
- **Costs**: *CLI-reported* (API-equivalent, per `claude` process), *estimated* (transcript tokens priced by
  `scripts/lib/usage.py`, deduplicated by message id), *billed* (always unknown here). Gaps make totals lower bounds.
- **Replies**: a plan-approval stop gets at most two automatic replies per session (and the arm's cap); any request
  touching access, money, scope, credentials, transmission or a choice becomes `needs_human`. Human replies via
  `resume` are counted separately.

## Isolation and measurement limits

Recorded in every report. Separate clones (no shared git common dir, `origin` removed), per-session HOME, config, TMP,
XDG and FSA state give operational separation only: all sessions run as the same OS user with shared network and
rate limits. The spend watcher polls and can overshoot. The task-identifier scan is a heuristic. Instruction sources are
what the CLI's init event and debug log report.

## Verification

```bash
python3 -m unittest discover -s tests/experiment -v   # fake claude CLI, no model calls
```
