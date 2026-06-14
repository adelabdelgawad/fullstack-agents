---
name: prompt-polish
description: Refine a raw user instruction into a precise, well-structured prompt before acting on it or delegating it to worker subagents. Applies Claude prompt-engineering best practices (clear intent, explicit scope, success criteria, format, context). Runs on every request via the prompt-polish UserPromptSubmit hook; this skill carries the method. Use whenever a request is about to drive code generation, review, debugging, or multi-agent work.
---

# Prompt Polish

A human prompt is often under-specified, ambiguous, or missing the context that
makes Claude do its best work. This skill refines the user's request into a
precise internal spec **before** you act on it or hand it to worker subagents.

The goal is not to inflate short requests or change what the user wants. It is to
remove ambiguity, surface the implied scope and success criteria, and structure
the request so the executor (you or a subagent) has everything it needs.

## When this runs

The `prompt-polish` UserPromptSubmit hook injects a short directive on every
prompt, so refinement is always in the loop. Scale the effort to the request:

- **Trivial / already-clear** (e.g. "yes", "continue", "fix the typo on line 12"):
  pass through unchanged. Do not pad it. Proceed.
- **Underspecified or large** (vague goal, missing scope, "change X across the
  app"): run the full refinement below before doing the work.

## The refinement procedure

Rewrite the request into a compact spec with these parts. Keep only the parts
that apply — omit the rest rather than inventing them.

1. **Intent** — one sentence: what outcome the user actually wants.
2. **Scope** — which files / layers / pages / entities are in scope, and what is
   explicitly out of scope. State the breadth explicitly (Claude Opus 4.8 follows
   scope literally and will not silently generalize "this page" to "all pages").
3. **Success criteria** — how "done and correct" is judged (behavior, tests,
   contract parity, lint/typecheck clean).
4. **Constraints** — patterns to follow, things not to touch, performance/security
   requirements, the project constitution if one exists.
5. **Output / format** — what the deliverable is (code, diff, report, answer) and
   any format requirements.
6. **Action vs. advice** — make explicit whether the user wants changes made or
   only suggestions. If they want action, say so with a direct verb ("implement",
   "edit") rather than "could you suggest".

Apply these best practices while rewriting:

- **Be clear, direct, specific.** Replace vague verbs with concrete ones. If the
  user wants "above and beyond", say so; otherwise keep the scope minimal.
- **Add the motivation.** When the user gives a reason, keep it — it lets the
  executor generalize correctly.
- **Structure with XML tags** when the spec mixes instructions, context, and
  inputs, so a subagent parses it unambiguously.
- **Carry examples forward.** If the user gave an example of the desired output,
  preserve it in `<example>` tags.
- **Prefer "do this" over "don't do that"** for format and behavior.

## Clarify vs. proceed

- If the request is genuinely ambiguous on a point that changes the outcome, ask
  **up to 3** focused clarifying questions before doing the work.
- If it is merely under-specified but the best interpretation is clear, state the
  interpretation you are proceeding with in one line, then proceed. Do not stall
  on questions you can answer yourself from the codebase.

## Passing the refined spec to workers

When you delegate to subagents (see the orchestration agent), pass the **refined
spec**, not the raw prompt. Well-specified, self-contained task descriptions are
what let workers run autonomously and correctly. Each worker should receive its
intent, scope (the exact unit it owns), success criteria, and constraints.

## Calibration notes (Claude Opus 4.x)

- **Literal scope:** spell out breadth ("apply to every page, not just the first")
  — the model will not infer it.
- **Calm language:** do not wrap the refined spec in "CRITICAL / YOU MUST"
  shouting; current models over-trigger on that. Normal, direct instructions work.
- **Don't over-engineer the spec:** a refined prompt is still minimal. Don't add
  features, abstractions, or defensive requirements the user didn't ask for.
- **Front-load specificity:** a clear, complete first instruction maximizes
  autonomy and reduces back-and-forth.

## Example

**Raw:** "make the tables use the new filter style"

**Refined spec:**
```
Intent: Migrate existing data-table pages to the new server-driven filter style.
Scope: All data-table pages under app/(pages)/**; only the filter panel + URL
  wiring. Out of scope: table columns, row actions, backend endpoints.
Success: Filters live in the URL (server-driven), no optimistic UI, rows repaint
  from the backend response; tsc + lint clean.
Constraints: Follow the data-table skill's URL-driven pattern and the project's
  existing filter component; do not introduce client-only state.
Output: Edits to each page + a list of pages changed.
Action: Implement the changes.
```

This is a large, repetitive change — hand it to the orchestration agent to split
per page, confirm concurrency with the user, and audit each unit.
