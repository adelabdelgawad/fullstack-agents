---
name: websocket
description: Python (FastAPI/Starlette) WebSocket servers — connection management, rooms and message protocols.
---

# Python WebSocket

Keep lifetime explicit: connect → accept → receive loop → disconnect → cleanup.
Reuse connection manager, rooms and protocol; validate messages and clean up on
disconnect/error. Read relevant manager, receive-loop, protocol and error-handling
rules before editing that part. This skill owns the Python server; browser
lifecycle belongs to `nextjs/references/live-updates.md`.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 5: When to Use This Skill
- Line 14: Core Mental Model
- Line 29: Architecture Overview
- Line 54: File Structure
- Line 67: Core Principles
- Line 135: Extended Concepts
- Line 178: Generation Order
- Line 189: Quick Reference
- Line 210: What "Production-Grade" Means
- Line 223: Explicit Non-Goals
- Line 231: References
