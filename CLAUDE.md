# CLAUDE.md - Fullstack Agents Repository Guide

This file provides guidance for Claude Code when working with this repository.

## Repository Overview

This repository contains the **fullstack-agents** Claude Code plugin - an AI-powered development toolkit for fullstack applications using FastAPI, Next.js, Docker, and more.

## Repository Structure

```
fullstack-agents/
├── .gitignore
├── CLAUDE.md                 # This file
├── LICENSE                   # MIT License
├── README.md                 # Marketplace README
├── docs/                     # Documentation
│   ├── agents.md
│   ├── commands.md
│   ├── skills.md
│   └── getting-started.md
├── plans/                    # Planning documents
└── plugins/
    └── fullstack-agents/     # The actual plugin
        ├── .claude-plugin/
        │   ├── plugin.json
        │   └── marketplace.json
        ├── agents/           # 28 specialized agents
        ├── commands/         # 8 slash commands
        └── skills/           # 7 skill domains
```

## Core Philosophy

**Compounding Engineering**: Each unit of engineering work should make subsequent units of work easier—not harder.

All agents follow this principle by:
1. Detecting and following existing patterns
2. Building on existing work rather than replacing
3. Automating repetitive tasks
4. Suggesting next steps to compound progress

## Agent Categories

| Category | Count | Purpose |
|----------|-------|---------|
| Generate | 7 | Smart code generation with dialogue |
| Review | 4 | Code quality, security, performance |
| Analyze | 4 | Codebase, architecture, dependencies |
| Scaffold | 5 | Project and module scaffolding |
| Debug | 4 | Error diagnosis, profiling |
| Optimize | 4 | Performance, cleanup, refactoring |

## Key Workflows

### Adding a New Agent

1. Create agent file in `plugins/fullstack-agents/agents/{category}/{agent-name}.md`
2. Follow the agent template:
   ```markdown
   ---
   name: agent-name
   description: When this agent should be used
   tools: Read, Write, Edit, Bash, Glob, Grep
   ---

   # Agent Title

   Description and instructions...
   ```
3. Update counts in:
   - `plugins/fullstack-agents/.claude-plugin/plugin.json`
   - `plugins/fullstack-agents/.claude-plugin/marketplace.json`
   - `README.md` (root)
   - `plugins/fullstack-agents/README.md`

### Adding a New Command

1. Create command file in `plugins/fullstack-agents/commands/{command-name}.md`
2. Follow the command template:
   ```markdown
   ---
   description: What this command does
   allowed-tools: Read, Write, Edit, Bash, Glob, Grep
   ---

   # Command Title

   Instructions for Claude...
   ```
3. Update counts in relevant files

### Adding a New Skill

1. Create skill directory in `plugins/fullstack-agents/skills/{skill-name}/`
2. Create required files:
   - `SKILL.md` - Skill overview
   - `examples.md` - Usage examples
   - `references/` - Detailed pattern docs
3. Update counts in relevant files

## Validation

Before committing, validate:

```bash
# Validate JSON files
jq '.' plugins/fullstack-agents/.claude-plugin/plugin.json
jq '.' plugins/fullstack-agents/.claude-plugin/marketplace.json

# Count agents
find plugins/fullstack-agents/agents -name "*.md" ! -path "*/_core/*" | wc -l

# Count commands
find plugins/fullstack-agents/commands -name "*.md" | wc -l

# Count skills
ls -d plugins/fullstack-agents/skills/*/ | wc -l
```

## Important Patterns

### Agent Lifecycle

All agents follow this 6-phase lifecycle:

1. **Detection** - Detect project type and existing patterns
2. **Dialogue** - Ask clarifying questions
3. **Analysis** - Analyze existing code to match style
4. **Confirmation** - Present plan for approval
5. **Execution** - Generate/modify code
6. **Next Steps** - Suggest related actions

### Session Flow (FastAPI)

The single-session-per-request pattern is critical:
- Session injected via `Depends(get_session)` in router
- Session passed to service methods
- Session passed to repository methods
- Never store session in `__init__`

### Data Fetching (Next.js)

Two supported strategies based on revalidation needs:

**Strategy A: Simple Fetching (Default)**
- Page is server component, fetches initial data
- Client uses `useState` with initialData
- UI updates from server mutation responses
- Use for: Settings, admin CRUD, forms, most tables

**Strategy B: SWR Fetching (When Justified)**
- Requires documented justification comment
- Client uses `useSWR` with `fallbackData`
- Configure appropriate revalidation triggers
- Use for: Dashboards, multi-user editing, live monitoring

Both strategies:
- Server component fetches initial data (no "use client" on page)
- Updates use server response (never optimistic)

See: `plugins/fullstack-agents/skills/nextjs/references/data-fetching-strategy.md`

## Commit Message Format

```
type: short description

Longer description if needed.

Co-Authored-By: Claude <noreply@anthropic.com>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Common Tasks

### Regenerate Documentation

```bash
# Update docs from plugin content
/release-docs
```

### Validate All Patterns

```bash
# Check all entities follow patterns
/validate
```

### Check Plugin Status

```bash
# Show current state
/status
```

## Learnings

1. **Keep counts synchronized** - Agent/command/skill counts must match across all files
2. **Follow existing patterns** - Analyze before generating
3. **Ask before assuming** - Use dialogue for clarification
4. **Suggest next steps** - Help users compound their progress
