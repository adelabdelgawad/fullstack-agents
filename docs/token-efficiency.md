# Token efficiency in Claude and Codex

Both editions retain the engineering rules but load them progressively. Claude
keeps its original lead, model settings, implementer selection, tool hooks,
marketplace and installer. Codex has a separate entry point and leads its own
flow, with Claude performing bounded audits.

## Claude skill changes

Ten large skills now have short entry points containing core invariants and
section indexes. Their complete previous bodies are retained in
`references/skill-guide.md`, with Markdown links adjusted for the new location:

- `using-fullstack-agents` and `task-flow`.
- `nextjs`, `data-table`, `fetch-architecture`.
- `docker`, `tasks-management`, `websocket`.
- `python-clean-architecture`, `rust-clean-architecture`.

Invoke skills through Claude's Skill tool as before. Read the guide's required
constraints/checklists and the sections the task actually needs; examples,
layouts and uncommon operational procedures stay on disk until relevant. Once
loaded, reuse a section while it remains in context. A reminder is not a reason
to re-invoke the skill or reload the full guide. The guide's detailed rules
remain authoritative; shorter entry points do not waive validation or gates.

The original ten entry points totalled 143,662 characters. The revised entries
use about 21,600 characters, an approximately **85% smaller initial payload**.
This measures characters loaded at skill entry, not total task tokens, cost or
latency; relevant detailed reads still contribute tokens.

`codebase-scanning` now explicitly caches one profile per service/lane, selects
representative files with `rg`, reads bounded ranges, and skips unrelated lanes.
Workers receive the lead's compact profile and known example paths rather than
repeating the same scan. Re-scan only changed assumptions or lost context.

The Claude flow remains:

```text
Claude investigates → Claude plans → small direct edit or configured implementer
    → Claude reads the touched diff and test logs → bounded repair brief → audit
```

The configured implementer remains headless Claude by default, with Codex/Grok
selected through existing bindings or explicit requests. No model, classifier,
hook event, environment default, permissions rule or dispatcher was changed.
The plugin/marketplace release version advances to 3.50.0 for distribution.
Projects such as UCM retain their own budgets, ownership rules and check commands.

## Codex loading behavior

The standalone builder reuses these shared section indexes, adapts skill paths,
and keeps full guides and helpers available. Other skills and workflow commands
also have compact entry points. Native Codex roles carry short instructions
pointing to their role guide instead of embedding all examples in configuration.

The Codex flow keeps planning and implementation with Codex. Claude receives a
bounded audit packet and returns issues with exact repair paths. The packet is
size-limited and never silently truncated; model usage/cost are saved when the
CLI returns them. A repair gets targeted validation and a focused re-audit,
with at most two repair rounds. See [codex.md](codex.md) for installation.

## Runtime settings left alone

Claude already injects a full prompt-polish/routing directive once per session
and then uses reminders. Resume/compact handling and transcript-based lane skill
lookup also remain unchanged. Its Haiku intent and reply classifiers retain
their existing settings; these edits reduce loaded content without changing
classification behavior. Codex uses a local reminder without classifier calls.

Tests validate preserved resources, working links, compatible skill names,
native role schemas, safe installation, scope detection and audit handoffs.
The existing Claude hook tests cover routing and transcript behavior. Installed
Claude plugin caches are not edited by changing this repository: distribute or
reinstall the revised plugin through the existing installation workflow.
