---
name: constitution
description: Create and maintain a per-project constitution — the versioned, normative principles file that codebase-scanning loads and all gates check against (layer rules, language lanes, wire contract, quality limits). Use when asked to create, update, or check a project constitution, bootstrap project principles, or when a governed project has no constitution yet. Do not use for the plugin's own global rules (those live in the skills).
---

# Project Constitution

The constitution is the project-owned, versioned principles file — NORMATIVE
(what the project intends), where the codebase-scanning profile is DESCRIPTIVE
(what the code currently does). Gates and agents check both.

## Location (search order)

1. `.specify/memory/constitution.md` — spec-kit standard (use when spec-kit is present)
2. `constitution.md` / `CONSTITUTION.md` — repo root
3. `.claude/constitution.md`

When creating a new one: use location 1 if `.specify/` exists, else location 2.

## Precedence

```
constitution (normative intent)
  > codebase-scanning profile (current reality)
    > skill reference patterns (defaults)
```

For NEW code, the constitution wins. When the constitution and the existing
codebase disagree, follow the constitution for new code, flag the divergence
to the user, and never silently "correct" old code (that is a refactor the
user must approve).

## Machine-Readable Limits

The constitution MAY contain a `## Limits` section with `key: value` lines the
hooks parse directly. Currently honored by stop-validate:

```markdown
## Limits
max-file-lines: 800
```

Omit the section to accept plugin defaults.

## Template

When creating a constitution, start from this template, fill the placeholders
from dialogue with the user, and DELETE sections that don't apply:

```markdown
# [PROJECT NAME] Constitution

Version: 1.0.0 — Amended: [DATE]
Amendments require a version bump and a one-line rationale in History.

## Architecture

- Style: clean architecture + DDD (layers: presentation / application / domain
  / infrastructure; dependencies point inward)
- Services: [list services and their languages, e.g. "billing: Rust (Axum),
  reporting: Python (FastAPI), frontend: Next.js"]
- The sole inversion seam is the repository port; use cases own transactions.

## Language Lanes

- Rust services follow rust-clean-architecture; Python services follow
  python-clean-architecture (or the simplified fastapi pattern where detected).
- Idioms never cross lanes. New services default to: [Rust | Python | ask].

## Wire Contract

- All APIs consumed by the frontend speak the shared dialect: camelCase JSON
  bodies, snake_case query params, limit/skip pagination, list envelopes with
  total. Contract source of truth: [the FastAPI service | bindings.d.ts | OpenAPI spec].
- Breaking a wire contract requires: [versioned endpoint | coordinated deploy | ADR].

## Quality

- Test coverage minimum: [80]% — unit + integration + E2E for critical flows.
- Warnings are errors (clippy -D warnings / ruff strict). No #[allow] / no
  blanket noqa — fix root causes.
- No hardcoded secrets; config is fail-fast typed (env validated at startup).

## Limits
max-file-lines: 800

## Non-Negotiables

- Search before implement; never knowingly duplicate business logic.
- No fixes without root cause (debug discipline).
- Internal error detail never reaches the wire.
- [project-specific rules, e.g. "all tables bilingual name_en/name_ar",
  "soft delete only, never hard DELETE"]

## History

- 1.0.0 ([DATE]): initial constitution.
```

## Maintaining

- Treat amendments like API changes: version bump + History entry, in the same
  PR as the change that motivated them.
- When a gate or review finds code violating the constitution, the resolution
  is explicit: fix the code OR amend the constitution — never ignore.
- Keep it under ~100 lines. A constitution nobody reads governs nothing;
  detailed patterns belong in the skills, not here.
