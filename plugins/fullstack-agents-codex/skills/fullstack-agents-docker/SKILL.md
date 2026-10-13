---
name: fullstack-agents-docker
description: "Production-ready Docker infrastructure for fullstack apps — multi-service Docker Compose, nginx reverse proxy, SSL termination, and service wiring for FastAPI + Next.js stacks. Use when setting up Docker infrastructure, adding containers or services, or configuring nginx, monitoring, or SSL. Do not use for application code changes inside the containers."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Docker infrastructure

Match existing compose, networks, volumes and environment conventions. Reuse
shared infrastructure; keep secrets out of committed configuration. Read Key
Patterns and Environment Variable Strategy before edits, then only relevant
service/network/Dockerfile examples. Follow project deployment authorization;
generating infrastructure does not authorize deploying it.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 5: When to Use This Skill
- Line 13: Architecture Overview
- Line 55: Directory Structure
- Line 92: Core Services
- Line 194: Environment Variable Strategy
- Line 211: Network Architecture
- Line 225: Dockerfile Patterns
- Line 253: Key Patterns
- Line 262: References
