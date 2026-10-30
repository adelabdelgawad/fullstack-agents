# Getting Started

This guide will help you get started with the fullstack-agents plugin.

## Installation

### 1. Add the Marketplace

```bash
/plugin marketplace add https://github.com/adelabdelgawad/fullstack-agents
```

### 2. Install the Plugin

```bash
/plugin install fullstack-agents
```

### 3. Verify Installation

Start a new session in a FastAPI, Rust or Next.js project. The session-start message names the
detected stack and the plugin scripts path.

---

## Working with the plugin

Ask in plain language. The session lead (`fullstack-agents:fullstack-agent`) classifies the
request, loads the matching skills through the prompt router, plans, edits directly or delegates
to an implementer, runs the checks and audits the diff before it reports.

```text
add a soft-delete flag to the product entity and hide deleted rows in the products table
the campaigns page takes 4 s to open, find out why
review the changes on this branch for security issues
```

Two slash commands remain:

| Command | Purpose |
|---------|---------|
| `/fullstack-agents:review` | Review code for quality, security, performance or pattern compliance |
| `/fullstack-agents:dashboard` | Start, stop or show the host-level agent dashboard |

See the [Skills Reference](skills.md) for what each skill covers.

---

## Troubleshooting

### Plugin Not Detected

If the session-start message does not mention fullstack-agents:

1. Verify installation:
   ```bash
   /plugin list
   ```

2. Reinstall if needed:
   ```bash
   /plugin uninstall fullstack-agents
   /plugin install fullstack-agents
   ```

---

## Enforcement Hooks (what to expect)

The plugin enforces its workflow with hooks — these behaviors are normal:

- **On session start**, your stack (FastAPI / Rust / Next.js) and project
  constitution are detected and the routing doctrine is injected.
- **On every stack-related prompt**, the routing gate is re-armed with the
  detected language lane and intent.
- **Edits to `.py`/`.rs`/`.ts`/`.tsx` files are BLOCKED** until the codebase
  scan and a lane-relevant skill have been invoked in the session. If you see
  a `[fullstack-agents] BLOCKED` message, invoke the listed skills and retry.
  Emergency override: set `FSA_SKIP_GATE=1`.
- **After each edit to a `.py`/`.rs` file**, `ruff` lints Python (violations
  block until fixed) and `rustfmt` auto-formats Rust. Run whole-project
  `clippy`/`tsc` yourself before shipping.

## Project Constitution (optional, recommended)

Say "create a constitution" in any project to generate a versioned principles
file (compatible with [spec-kit](https://github.com/github/spec-kit)'s
`.specify/memory/constitution.md` location). Its rules take precedence over
detected codebase patterns for new code.

---

## Next Steps

- Read the [Agents Reference](agents.md) for detailed agent documentation
- Read the [Commands Reference](commands.md) for the two slash commands
- Read the [Skills Reference](skills.md) for pattern documentation

---

## Getting Help

- GitHub Issues: [Report a bug](https://github.com/adelabdelgawad/fullstack-agents/issues)
- Documentation: [Full documentation](https://github.com/adelabdelgawad/fullstack-agents/docs)
