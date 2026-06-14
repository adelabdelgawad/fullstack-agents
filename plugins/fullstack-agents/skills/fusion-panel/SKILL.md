---
name: fusion-panel
description: Panel reasoning for high-stakes decisions — take several INDEPENDENT passes at the same question (blind to each other), then synthesize consensus, contradictions, unique insights, and blind spots into one grounded answer. Inspired by fusion-fable's "independence, then synthesis". Zero setup — uses parallel Claude subagents, no external CLIs and no slash command. Use for architecture choices, risky migrations, security-sensitive changes, stubborn bugs, and ambiguous trade-offs where being wrong is costly.
---

# Fusion Panel

A single reasoning pass commits to one path early. A panel beats it because
diversity is **harvested, not manufactured**: running the same question
independently yields different reasoning, different tool calls, and different
sources. The wins come from comparing those independent passes and reconciling
where they disagree.

This skill is always available to the agents — no command, no setup. Reach for it
automatically when a decision is high-stakes; skip it for routine work.

## When to use it

Use a panel when being wrong is expensive and the answer is non-obvious:

- Architecture or design choices with long-lived consequences.
- Risky or irreversible changes (schema migrations, auth/RBAC, data backfills).
- Security-sensitive logic.
- A stubborn bug where the root cause is genuinely unclear.
- An ambiguous trade-off the user is relying on you to get right.

Do **not** convene a panel for routine generation, single-file edits, or anything
where one careful pass is plainly enough. The panel costs latency and tokens; spend
it where confidence errors carry real cost.

## The procedure

### 1. Frame one shared question

Refine the question into a single, self-contained prompt (skill: `prompt-polish`):
the decision to make, the relevant context, the constraints, and what a good answer
must cover. Every panelist gets the **same** prompt.

### 2. Take independent passes (blind)

Dispatch **2–3 panelists in parallel**, each blind to the others, with the Agent
tool in a single turn:

- **Zero-setup default:** independent Claude subagents. Use **Opus** panelists for
  the hardest calls; mixing one **Sonnet** panelist adds reasoning diversity.
- Vary the lens, not the question, to harvest genuine diversity — e.g. one panelist
  reasons correctness-first, one risk/failure-first, one simplicity/maintainability-first.
- Each panelist returns its answer plus its reasoning and any sources or code it
  relied on, so the synthesis can attribute findings.
- **Optional external models** only if the user already has the CLIs (e.g. a
  `codex` or `gemini` tool): add them as extra panelists. Never require them — the
  default panel is Claude-only.

### 3. Synthesize

In a final pass (Opus for substantial decisions), consolidate the panelists into a
grounded answer with this structure, each point attributed to the panelist(s) that
raised it:

- **Consensus** — what all panelists agree on (highest confidence).
- **Contradictions** — where they disagree, and which side is better supported.
- **Partial coverage** — points only some panelists reached.
- **Unique insights** — a single panelist's non-obvious, valid point.
- **Blind spots** — what none addressed but should have.
- **Final answer** — the grounded recommendation, with its confidence level and
  the reasoning that resolved the contradictions.

## Output

Lead with the **Final answer** and its confidence. Keep the consensus/
contradictions/blind-spots breakdown available but concise — it is the evidence
for the recommendation, not the headline. If the panel does not converge, say so
and surface the decision (with the trade-offs) to the user rather than forcing a
false consensus.

## Calibration (Claude Opus 4.x)

- **Independence is the point.** Do not let panelists see each other's work before
  the synthesis step, or you lose the diversity that makes the panel worth it.
- **Opt-in fan-out:** current models spawn fewer subagents by default; convening a
  panel is a deliberate choice for high-stakes calls — make it explicitly.
- **Don't over-convene.** Two strong independent passes beat five lazy ones. Right-
  size the panel to the stakes.
- **Reconcile, don't average.** The synthesis judges which reasoning is correct; it
  does not split the difference.
