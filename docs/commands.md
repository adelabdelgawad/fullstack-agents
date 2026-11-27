# Commands Reference

The plugin has two slash commands. Everything else is asked in plain language and routed to
skills by the session lead.

| Command | Description |
|---------|-------------|
| `/review` | Review code for quality, security, performance or pattern compliance |
| `/dashboard` | Start, stop or show the host-level agent dashboard |

---

## /review

Review code for quality, security, and performance issues.

### Usage

```bash
# Review code quality
/review quality <path>

# Review security
/review security <path>

# Review performance
/review performance <path>

# Review pattern compliance
/review patterns <entity>
```

### Examples

```bash
# Review quality of product module
/review quality app/services/product_service.py

# Review security of entire API
/review security app/api/

# Review patterns for user entity
/review patterns user
```

### Output

- Issue identification with severity
- Code location references
- Specific fix recommendations
- Pattern violation details

---

## /dashboard

Start, stop or show the read-only, host-level agent dashboard. It survives the session that
started it.

```bash
/fullstack-agents:dashboard start
/fullstack-agents:dashboard status
/fullstack-agents:dashboard stop
```

---

## /implementer

Show or switch this session's implementer engine, the one `scripts/codex-task.sh` dispatches through.
`claude` sets implement model `claude-sonnet-5-5`; `codex` sets `gpt-6.1-sol`. Every other agent setting is kept.
It is the same switch as the Office Agent settings Implementer control (`agent_config.set_implementer`).

```bash
/fullstack-agents:implementer          # show
/fullstack-agents:implementer codex
/fullstack-agents:implementer claude
```
