# Standalone Codex-led Fullstack Agents

This is a separate edition. Claude's marketplace, `install.sh`, hooks, settings,
agent definitions and dispatcher stay unchanged. Shared Claude skills use the
token-saving entry points described in [token-efficiency.md](token-efficiency.md).

The standalone flow is:

```text
Codex investigates and plans
    → Codex implements directly or with bounded Codex workers
    → Codex validates
    → Claude audits a bounded evidence packet
    → Claude returns issues, evidence and repair scope
    → Codex verifies and fixes the issues
    → affected validation and focused re-audit
    → Codex reports the final result
```

Opus, through Claude, is only the independent bounded read-only auditor. Codex owns investigation, planning, implementation, validation and repairs. Its audit CLI has no tools,
hooks, MCP connections or slash commands. It receives only the saved plan,
explicit changed files, diff and optional supporting line ranges. It cannot
edit the project. The Codex lead owns the conclusion and verifies findings.

## Install

Requires Python 3.11+, Bash, Git and a Codex CLI supporting repo skills, native
agent TOML files and lifecycle hooks. Audits require an authenticated Claude
Code CLI supporting structured output and the options used in `handoff.py`.
Development checks used Codex CLI 0.162.1 and Claude Code 2.1.296; no paid model
call is required for installation or the local test suite.

From this repository:

```bash
bash install-codex.sh /path/to/project --dry-run
bash install-codex.sh /path/to/project
cd /path/to/project
codex
```

Alternatively install the packaged plugin from the Codex marketplace:

```bash
codex plugin marketplace add adelabdelgawad/fullstack-agents
codex plugin add fullstack-agents-codex@fullstack-agents-codex
```

Use either marketplace installation or the project-local installer to avoid
duplicate skills/hooks. Marketplace installation supplies all skills, role
guides, helper scripts and bundled hooks. Project-local installation additionally
places native custom role files in the project's `.codex/agents/`; marketplace
users can pass a bundled role guide to a built-in Codex worker when that custom
role is unavailable. Restart Codex after installing; review hooks with `/hooks`.

Use `/hooks` to inspect and trust the new Codex hooks. Codex requires this trust
for project-local command hooks; the installer does not bypass it. If hooks are
disabled, start with `$fullstack-agents-using-fullstack-agents` to load the flow
explicitly. The session-start hook loads the Codex-specific guide without editing
the application's shared `AGENTS.md` or `CLAUDE.md`.

Installation writes only:

- `.codex/fullstack-agents/`: generated standalone bundle and its inventory.
- `.agents/skills/fullstack-agents-*`: discoverable links to bundle skills.
- `.codex/agents/fullstack-agents-*.toml`: native roles, inheriting your Codex
  model; analysis/review roles use a read-only sandbox.
- `.codex/hooks.json`: Codex-only hooks, preserving unrelated existing groups.
- `.codex/config.toml`: a default only when no file exists; existing model,
  permissions, MCP and other configuration are preserved.
- `.codex/.fullstack-agents-install.json`: ownership hashes for safe updates.

The installer preflights collisions before writing. Rerun it to update from the
unchanged engineering sources. It refuses to replace modified adapter files or
unowned conflicting files and does not touch any `.claude` directory. Author
adapter changes in `integrations/codex/`; generated copies are not the source.
For a reviewable build without installing, use:

```bash
python3 integrations/codex/scripts/build.py /tmp/fullstack-codex-bundle
```

The build directory must be empty. Shared engineering skills, references, examples,
helpers and agent roles come from `plugins/fullstack-agents/`; runtime-dependent
skills have explicit Codex overrides. `inventory.json` records source hashes.
Generated skill entry points are short section indexes; full engineering guides
live in references and are read in targeted ranges. Native role instructions
also point to their guide instead of embedding every example in the agent config.
The optional shared dashboard shows Codex sessions from `$CODEX_HOME/sessions`
rollouts beside Claude sessions and other harnesses herdr reports. It reads
validated `$CODEX_HOME/fsa-flow` journals for explicit Codex progress without
calling a model classifier, and displays the configured lead model and history.
`plugins/fullstack-agents-codex/` is the checked-in generated release package;
`.agents/plugins/marketplace.json` exposes it without changing the Claude
marketplace. Regenerate the package from adapter/shared sources for releases.

## Skills and workflow entry points

Use normal language or the namespaced skills:

```text
$fullstack-agents-generate create a Product CRUD API
$fullstack-agents-review audit the authentication change
$fullstack-agents-analyze map this service's architecture
$fullstack-agents-scaffold create a Rust microservice
$fullstack-agents-debug diagnose the slow table
$fullstack-agents-optimize remove repeated fetch logic
$fullstack-agents-validate check this entity
$fullstack-agents-status show detected services and applicable skills
```

These are Codex skills, not Claude slash commands. `$fullstack-agents-task-flow`
holds the Codex-led flow. Skill-local references resolve beside the skill;
bundle paths resolve inside `.codex/fullstack-agents/`.

## Turn continuity (Stop hook)

A Codex turn ends at the lead's final message and nothing restarts it; finishing
workers do not wake the lead. The bundle's `Stop` hook (`scripts/hook.py stop`,
shared logic in `plugins/fullstack-agents/scripts/lib/stop_guard.py`) reads the
session's registered task ledger. With `pending` or `in_progress` rows it sends
the turn back with the open ids unless the final line is `Waiting on: you - ...`,
`Paused: ...` or `Blocked: ...`, or the reply closes with a question. A user
prompt that asks to stop or pause releases it; every other prompt re-arms it. An
unchanged ledger is sent back at most three times. `FSA_STOP_GUARD=off` disables
it. Codex runs a new hook only after it is trusted: open `/hooks` once after
upgrading and trust the `Stop` entry. Verified on Codex CLI 0.162.1: the hook
receives `session_id`, `cwd` and `last_assistant_message`, and `decision: block`
continues the turn with the reason as the next instruction. The Claude plugin
registers the same guard (`hooks/stop-guard`), where `Waiting on: <background
task>` also releases the turn because task notifications wake Claude.

## Claude launcher (`cc` alias)

Every Claude call the plugins make (Codex audits in `handoff.py`, the Haiku
classifier, dashboard-started sessions) runs through the user's `cc` shell
alias, normally `alias cc='claude --dangerously-skip-permissions'`. Scripts do
not see shell aliases and `/usr/bin/cc` is the C compiler, so
`plugins/fullstack-agents/scripts/lib/claude_cli.py` reads the alias from an
interactive `bash -ic 'alias cc'` and runs its expansion. A missing alias (or
one naming a missing binary) is an incomplete audit, a skipped classification,
and a session-start notice telling the lead to ask the user to add it; plain
`claude` is never used as a fallback. Audit and classifier calls pass
`--tools ""`, so the alias's permission bypass has nothing to bypass. The Claude
implementer engine in `codex-task.sh` still launches `claude` directly: its
`ALLOWED_PATHS` write fence relies on `--permission-mode dontAsk`, which
`--dangerously-skip-permissions` overrides.

## Bounded Claude audit and repair handoff

Save a concise plan containing files, acceptance criteria and check results.
After implementation and validation, run from the project:

```bash
python3 .codex/fullstack-agents/scripts/handoff.py \
  --root . --plan /tmp/product-plan.md \
  --files app/models/product.py app/routes/products.py \
  --context app/auth.py:20:65
```

`--base HEAD` audits current staged/unstaged changes and explicitly listed
untracked files. For a committed change, pass its pre-change commit as `--base`.
Only listed files are audited; the Codex lead must ensure that the list covers
the completed task. Existing unrelated dirty work should be isolated first.
The tool never silently truncates a large diff: split it into coherent audit
units or explicitly raise the packet limit.

The printed manifest points to `handoff.json`, `repair-brief.md`, the evidence
packet and saved CLI logs. Exit codes are:

| Code | Meaning |
|---|---|
| 0 | Valid PASS with no findings |
| 3 | Valid CHANGES with issues and repair scope |
| 2 | Incomplete audit: CLI/auth/budget failure, invalid result or stale files |

Findings contain `file`, `line`, `severity`, `issue`, `evidence` and
`repair_scope`. Codex reopens the cited source before acting. Scope is proposed
by the auditor, not automatic authorization to expand the user's task. A
repair requiring another path must be surfaced. Rerun the audit after repair
with `--previous /tmp/.../handoff.json`; include only necessary additional
context. Stop after two repair rounds and report unresolved issues.

Default bounds: eight submitted files, eight supporting ranges of at most 120
lines, 32,000 packet characters, twelve findings, a $2 audit ceiling and five
minutes. `--max-files`, `--max-chars`, `--budget`, `--timeout` override these for
one run. Claude defaults to `opus`; use `FSA_CLAUDE_AUDIT_MODEL` or `--model`
to select an available audit model. Codex inherits its configured model.
An incomplete audit is never converted into a pass or silently replaced with
another engine. Cost and usage returned by Claude are saved with the handoff.

## Bounded Codex workers

Native Codex roles are available for authorized delegation. Small changes stay
with the lead; sequential work is the default. A headless alternative is:

```bash
python3 .codex/fullstack-agents/scripts/worker.py implement /tmp/product-brief.md --root .
```

The brief needs `PLAN:` and an `ALLOWED_PATHS:` block with at most eight exact
repository-relative paths, plus task and acceptance criteria. Use `SKILLS:` to
name only needed skills, and include the lead's compact style profile. The
worker is told to read the listed skill files instead of receiving every skill
in its prompt. `investigate` requires a `FILES:` block and uses a read-only
sandbox. Planning remains the lead's job.

Workers cannot spawn nested agents. Model selection inherits Codex settings
unless `--model` is given. Changed content is compared before and after the run,
including files already dirty and untracked files. An out-of-scope change
returns exit 3 and a manifest; no changes are reverted automatically. This is
post-run scope detection, not a filesystem allowlist. Use isolated worktrees
for concurrent writers. CLI errors or malformed results return exit 2.
Ignored files are compared using metadata (content hashes for explicitly scoped
paths), so ordinary ignored-file writes are detected without hashing every build
artifact. Git HEAD/config/refs changes are also flagged; routine index refreshes
are excluded. This is scope evidence, not a security boundary or a complete audit
of every internal Git file. Audit packets fingerprint changed files, supporting
context, the plan and prior handoff before assembling and after reviewing them.

## Token-saving behavior and validation

- Search before reading; keep file reads and context ranges bounded.
- Default to 200 source lines per read and a three-file direct-edit budget;
  project bindings may refine these. Workers receive example paths for tests.
- Scan each service once and reuse its style profile while in context.
- Load only lane-relevant skills and references, once while in context.
- Write short plans and path-bounded briefs; avoid delegating trivial changes.
- Keep full logs on disk; bring summaries and failing lines into context.
- Batch failures and run affected checks once after fixing them.
- Route prompts locally with a short reminder; no classifier model calls.
- One focused Claude audit for completed work; re-audit only repairs or new
  evidence, with explicit packet, cost and retry limits.

The post-patch hook runs available Ruff checks on edited Python files, and
reminds the lead to run Cargo formatting checks for Rust. It does not install
tools, guess a Rust edition, scan a transcript or autoformat files. It reports
missing tools. TypeScript checking remains a project-level check.

Run project-specific checks from the detected service roots. The helper provides
defaults without fetching missing tools:

```bash
bash .codex/fullstack-agents/scripts/validate.sh python path/to/backend
bash .codex/fullstack-agents/scripts/validate.sh rust path/to/rust-service
bash .codex/fullstack-agents/scripts/validate.sh frontend path/to/frontend
```

The Python helper checks Ruff and mypy, Rust checks formatting/Clippy/tests,
and frontend checks the local TypeScript compiler and the npm lint script.
Use the project's own package manager/scripts when those differ, and run the
affected tests required by the saved plan. Missing checks are not passes.

Hook feedback and instructions do not guarantee that a skill was read or
prevent arbitrary shell writes. Explicit checks and Claude audits remain part
of the completion contract. The original Claude transcript-based pre-edit
gate, team guard and reply classifier are not claimed as ported. The optional
shared dashboard supports explicit Codex workflow journals.

Official runtime references: [skill discovery](https://learn.chatgpt.com/docs/build-skills),
[native agents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
and [hook configuration and trust](https://learn.chatgpt.com/docs/hooks).

## UCM configuration used as a reference

Read-only inspection of `/home/adel/workspace/ucm` found these active inputs:

| Source | Reusable behavior | Treatment in this repository |
|---|---|---|
| `CLAUDE.md`, task-flow bindings | Three-file edit budget, 200-line reads, bounded briefs, cached scans, evidence before conclusions | Adapt portable rules into the Codex guide; keep UCM operational rules in UCM |
| `.claude/settings.json` | Active hooks, plugin registration, Codex implementer selection | Reference only; the standalone Codex installer has its own runtime configuration |
| `.claude/hooks/guard-source-reads.sh` and test | Prevent broad source dumps | Carry the read budget into section-indexed skills and bounded context packets |
| `.claude/hooks/guard-source-writes.sh` and test | Avoid edits that bypass the lead's gate | Use Codex patch tools and audit actual changed content; no claim of a complete shell-write firewall |
| `.claude/hooks/gate-agent-scan.sh` and test | `FILES:` plus `REPORT:` contracts | Enforce both for headless investigative workers |
| `.claude/hooks/gate-codex-implement.sh` and test | Small direct edits, risk carve-outs, live worker ownership | Carry scope/budget into the flow; preserve UCM's project-specific gate in UCM |
| `.claude/hooks/guard-host-resources.sh` and test; `scripts/agent-host-guard.sh` | Host-specific resource limits | Project-local; do not impose production-host rules on all users |
| `scripts/codex-task.sh` | Thin project wrapper around plugin scripts | Existing plugin dispatcher remains unchanged; standalone uses `worker.py` |
| `.claude/codex-result.schema.json` | Structured worker report | Already present in this plugin; standalone carries its own bounded schema |
| `.claude/fsa-team.conf` | UCM deploy lock command matching | Project-local; do not copy UCM deployment commands into generic defaults |

UCM's `scripts/agent-cargo.sh`, `scripts/test-backend.sh`, worktree helpers,
architecture index and ownership docs remain the authoritative project inputs
when working on UCM. In particular, use its guarded test commands rather than
the generic helper against a production database. No UCM file was modified or
copied wholesale into this integration.

The inspected global `/home/adel/.claude/settings.json` registers only a Herdr SessionStart
hook, `/home/adel/.claude/hooks/herdr-agent-state.sh`; this is optional UI/session
integration. No global `.claude/rules` directory was present. Global credentials,
session history and caches were excluded from inspection. UCM's `.archive-tools`
and `.claude/helpers` are not registered by the inspected settings, so they are
not runtime dependencies of this adapter. UCM had no `.codex` directory.
The installed plugin is version 3.49.0 at
`/home/adel/.claude/plugins/cache/fullstack-agents/fullstack-agents/3.49.0`.
Its lead, task-flow, dispatcher and hook configuration matched this repository
before the token-saving skill edits. Neither UCM nor the installed cache was changed.

## Local verification

```bash
python3 -m unittest discover -s tests/codex -v
```

Tests use fake Claude/Codex executables for audit handoffs and scope detection;
they do not spend model tokens. A real authenticated model audit remains a
separate runtime check.

## Explicit workflow progress

Report every transition with the bundle's CLI:

```bash
python3 scripts/phase.py --root ROOT --phase investigate
```

Use `plan`, `implement`, `validate`, and `audit` as the work advances; report
`implement` again for repairs, followed by validation and audit. Report
`complete` only after the work is actually complete. The session defaults to
`CODEX_THREAD_ID`; use `--session ID` when it is absent. Atomic journals live in
`$CODEX_HOME/fsa-flow` (default `~/.codex/fsa-flow`); `--state-dir` overrides this
location. The optional shared dashboard reads its default journal location.
Phase writes need no user approval. Their bounded history records progress and
never replaces checks, audit evidence, or authorization for commit/deploy.
The dashboard shows validation/audit as Review and completed Codex work as Done.

Workers and bounded audits register their originating `CODEX_THREAD_ID` in private,
atomic `$CODEX_HOME/fsa-flow/runs/<session>/<run_id>.json` records. Missing session
IDs disable registration; telemetry failures are reported without changing the task
result. Records include artifacts, actual worker thread IDs, model (null when unknown),
summary and terminal state. Audit verdicts appear only after handoff validation;
failed or malformed audits remain incomplete. The dashboard groups registered runs
and recursive native descendants under their lead, without attributing shared
app-server processes to unrelated sessions.

The phase CLI accepts repeatable `--check TEXT` and `--summary TEXT` to record
lead-reported verification and result text. These are reports, not proof of a
passing check. Omitted fields retain validated evidence for the same session and
cwd; explicit checks replace the list. `investigate` clears prior task evidence.
`--auditor-model MODEL` records selected intent, defaulting to
`FSA_CLAUDE_AUDIT_MODEL` or `opus`; registered audit runs remain authoritative
for the actual model, state and verdict. Information shows the latest eight phase
transitions and keeps older recorded transitions in a collapsed disclosure.
When no transcript model is available, the dashboard reads the exact thread's
model from the latest Codex state database in read-only mode, without config guesses.
