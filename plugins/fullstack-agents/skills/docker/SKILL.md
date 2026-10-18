---
name: docker
description: Docker Compose, containers, nginx reverse proxy, SSL and service wiring for fullstack apps. Not for application code inside containers.
---

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
