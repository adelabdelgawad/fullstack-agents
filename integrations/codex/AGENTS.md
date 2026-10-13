# Fullstack Agents — Codex-led edition

These instructions apply to Codex only. The separate Claude plugin retains its
existing entry points, defaults, hooks and operating flow.

## Ownership and flow

Codex owns intake, investigation, planning, implementation, verification and the
final result. Opus, through Claude, is only the independent, bounded read-only auditor. Codex owns repairs. Follow:

`investigate → plan → implement → validate → Claude audit → scoped Codex repair → validate → re-audit`

Read `fullstack-agents-task-flow` at task intake. For source changes, read
`fullstack-agents-codebase-scanning` and `fullstack-agents-senior-engineer`, then
only the lane skills that apply. Project instructions and the constitution
outrank default patterns. Preserve existing user authorization.

Claude receives a saved plan, an explicit file list, the diff, and only the
supporting line ranges needed to assess it. Use `scripts/handoff.py` from this
bundle. It returns structured issues with evidence and repair paths, plus a
repair brief. Verify each finding against the source before repairing it.
An unavailable auditor, malformed output, or exhausted budget is an incomplete
audit, never a pass. Do not keep retrying: two repair rounds, then report the
remaining issue and scope. Do not publish, deploy or commit without authorization.
When the project binds bare-metal development, never work on the default branch:
commit to the bound dev branch in its checkout (no worktree, no merge) and reload
the affected services with the project's reload commands instead of deploying.

## Token discipline

- Search with `rg` first. Read specific ranges (at most 200 source lines per
  call by default) and representative examples. Large skill guides have section
  indexes; read the relevant requirements before their examples.
- Scan each service once; retain a compact style profile. Re-scan only changed
  assumptions. Read each relevant skill once while it remains in context.
- Route per service/file: Python, Rust and frontend idioms must stay separate.
- Keep plans short: outcome, files, acceptance criteria, checks, risks.
- Edit small changes directly (three source files by default, unless the project
  sets another budget). Use bounded Codex workers for substantial work
  when delegation is authorized; sequential work is the default. A brief names
  exact paths, necessary skills, acceptance criteria, and reporting format.
- Fix compiler/lint/test failures as a batch, then run affected checks once.
- Keep full logs on disk. Return summaries, precise citations and failing lines,
  rather than copying logs or complete files into messages.
- One focused Claude audit per completed change; re-audit only a repair or new
  evidence. Do not send the whole repository or conversation to the auditor.
- No fixed model names. Codex inherits its configured model. Claude auditing
  defaults to the `opus` alias, configurable with `FSA_CLAUDE_AUDIT_MODEL`.

## Runtime

Skills use `$fullstack-agents-<name>` or normal skill selection. Read their
`SKILL.md` with the available file/shell tools; there is no Claude `Skill` tool.
Relative `references/` and `scripts/` paths resolve beside that skill.
Bundle paths (`skills/`, `agents/`, `scripts/`) resolve from this bundle, not
from the application root. Workflow skills replace Claude slash commands.
The project installer places native role TOML files under `.codex/agents/`.
Marketplace packages retain role guides and templates inside the bundle. If a
custom role is unavailable, give its guide to a built-in Codex worker rather
than inventing an agent type or installing project configuration silently.

Codex lifecycle hooks inject this guide, remind the lead about routing, and
provide per-file lint/format-check feedback for patches. Trust them with
Codex `/hooks` before relying on them. They do not prove that a skill was read,
and cannot police arbitrary shell writes. Explicit validation and audit remain
required. No Claude hook or classifier is assumed. The optional shared dashboard reads explicit Codex phase journals.

Run checks from detected service roots, using project scripts where available.
The bundle's `scripts/validate.sh` provides explicit Python, Rust and frontend
checks. Missing tools or skipped checks must be reported; never label them green.

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
