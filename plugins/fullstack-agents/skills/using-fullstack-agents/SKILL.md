---
name: using-fullstack-agents
description: Auto-triggering guide for fullstack-agents — ensures Claude automatically invokes the right code generation, review, and debugging skills before writing any FastAPI or Next.js code.
---

<EXTREMELY-IMPORTANT>
If you are about to write, modify, or generate ANY code in a FastAPI backend or Next.js frontend, you MUST consult fullstack-agents skills first.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.

IF A FULLSTACK-AGENTS SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.
</EXTREMELY-IMPORTANT>

# Using Fullstack Agents

## The Rule

**Before writing ANY backend or frontend code, check if a fullstack-agents skill covers it.** Even a 1% chance means invoke the skill. If it turns out to be wrong for the situation, you don't need to follow it — but you MUST check first.

## Skill Routing Table

When you detect the user's intent, route to the correct skill:

| User Intent Pattern | Skill to Invoke |
|---|---|
| "create entity", "add model", "CRUD", "backend API for X" | `fullstack-agents:generate entity` |
| "data table", "management page", "list page with CRUD" | `fullstack-agents:generate data-table` |
| "create page", "new page", "frontend page" | `fullstack-agents:generate page` |
| "API route", "proxy route", "Next.js API" | `fullstack-agents:generate api-route` |
| "celery task", "background task", "async task" | `fullstack-agents:generate task` |
| "scheduled job", "cron job", "periodic task" | `fullstack-agents:generate job` |
| "docker service", "add container" | `fullstack-agents:generate docker-service` |
| "fullstack feature", "create X end-to-end" | `fullstack-agents:generate fullstack` |
| "debug", "error", "fix", "broken", "not working" | `fullstack-agents:debug` |
| "review", "check quality", "audit" | `fullstack-agents:review quality` |
| "security review", "security audit" | `fullstack-agents:review security` |
| "performance review", "slow", "optimize" | `fullstack-agents:review performance` or `fullstack-agents:optimize` |
| "check patterns", "validate patterns" | `fullstack-agents:review patterns` |
| "analyze codebase", "architecture review" | `fullstack-agents:analyze` |
| "scaffold project", "new project", "bootstrap" | `fullstack-agents:scaffold` |
| "validate entity", "check entity compliance" | `fullstack-agents:validate` |
| "validate fetch", "check fetch patterns", "fetch audit" | `fullstack-agents:fetch-validate` |
| "plan fetch", "fetch layers for X" | `fullstack-agents:fetch-plan` |
| "scaffold fetch", "generate fetch boilerplate" | `fullstack-agents:fetch-implement` |

## Hard Gate — 4-Step Check Before ANY Code Generation

Before writing ANY code that touches FastAPI or Next.js, run this mental gate:

```
1. DETECT  → What type of code is being requested?
             (model, schema, router, page, component, API route, task, etc.)

2. MATCH   → Does a fullstack-agents skill cover this?
             (Check the routing table above)

3. INVOKE  → If YES: invoke the skill BEFORE writing any code
             If NO: proceed normally but still respect codebase patterns

4. SCAN    → Has codebase-scanning run this session?
             If NO: invoke fullstack-agents:codebase-scanning first
             If YES: use the detected style profile
```

**Do NOT skip to step 3.** Detection and matching must happen first.

## Rationalization Prevention

These thoughts mean STOP — you're rationalizing skipping the skill:

| Thought | Reality |
|---|---|
| "This is just a simple endpoint" | Simple endpoints still need pattern compliance (CamelModel, session handling, response schemas). |
| "I'll just add one field to the model" | Model changes cascade to schemas, routers, and frontend types. Check the skill. |
| "It's only a small component" | Small components still need to follow existing naming, import, and state patterns. |
| "I know how FastAPI works" | Knowing FastAPI ≠ knowing THIS project's FastAPI patterns. Invoke the skill. |
| "I know how Next.js works" | Knowing Next.js ≠ knowing THIS project's data-fetching and state patterns. |
| "The user said to do it quickly" | Fast AND correct > fast AND wrong. Skills prevent rework. |
| "This is a trivial change" | Trivial changes with wrong patterns create tech debt. Check first. |
| "I'll fix the patterns later" | Later never comes. Get it right the first time. |
| "This doesn't need a full generation" | Even partial generation benefits from pattern detection. |
| "I remember the patterns from earlier" | Patterns evolve. Skills have the current reference. Re-read. |
| "Let me just scaffold this by hand" | The generate agents handle scaffolding WITH pattern compliance. |
| "It's just a type definition" | Types must match CamelModel conventions and API contracts. |

## Automatic Chaining Rules

After ANY code generation completes, the following chain fires **automatically**:

```
GENERATE → REVIEW PATTERNS → FIX VIOLATIONS → VALIDATE → PRESENT NEXT STEPS
```

Specifically:

1. **Generate** — the agent produces code
2. **Review patterns** — automatically run pattern compliance review on generated code (equivalent to `/review patterns {entity}`)
3. **Fix violations** — if any violations found, fix them immediately
4. **Validate** — run type check + lint verification:
   - Backend: `uv run mypy . && uv run ruff check .` (from src/backend/)
   - Frontend: `npx tsc --noEmit && npm run lint` (from src/frontend/)
5. **Present next steps** — only THEN show the user what was created and suggest follow-up actions

**Do NOT ask the user's permission between steps 1-4. They are mandatory.**

## Codebase Scanning Mandate

On the **first code generation** in any session:
- You MUST invoke the `fullstack-agents:codebase-scanning` skill BEFORE generating code
- This detects project structure, naming conventions, and existing patterns
- The detected style profile overrides any reference patterns in the skills
- Subsequent generations in the same session can reuse the cached profile

## Skill Priority

When both `superpowers` and `fullstack-agents` apply:

- **superpowers** handles workflow orchestration (brainstorm → plan → execute)
- **fullstack-agents** handles code generation specifics (pattern detection, generation, review)

They complement each other. Use superpowers for the workflow, fullstack-agents for the code.

## How to Access Skills

Use the `Skill` tool to invoke any fullstack-agents skill. When you invoke a skill, its content is loaded and presented to you — follow it directly. Never use the Read tool on skill files.

## Skill Types

**Rigid** (generate agents, review agents): Follow the agent lifecycle exactly. Don't skip phases.

**Flexible** (analyze, optimize): Adapt the approach to the specific situation.

The skill/agent itself tells you which type it is.
