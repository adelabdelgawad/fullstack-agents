---
name: session-review
description: Questions about past Claude Code sessions — which session worked on X, a session id, token use or cost per session, day or week, and reviewing recent prompts for recurring work worth a rule, script or skill.
---

# Session review

Past sessions are answered from their transcript files with the plugin's `scripts/fsa-sessions`; it reads
files only (no model calls) and prices tokens with the same table as `fsa-usage`. Every cost is an estimate.

| Question | Command |
|---|---|
| Which session worked on X / its id | `fsa-sessions find "<words the user typed>" [--days 30] [--project <part>]` |
| Cost and tokens per session | `fsa-sessions list [--days 7] [--project <part>]` (lead plus its subagents) |
| What the user asked, for pattern review | `fsa-sessions prompts [--days 10] > <scratchpad>/prompts.tsv` |

`find` matches what the user typed, not what the agent replied; try the user's own words, then a
distinctive noun. Several hits: give each session's id, project, date and matching prompt, and let the
user pick.

## Reviewing recurring work

1. Dump prompts to a file and count patterns with `grep -ciE` over that file; never read every prompt
   into context.
2. For each pattern, look at what the agent said just before the user's prompt: an approval the agent
   asked for is fixed by a rule or authorization, not by a new skill.
3. Rank by turns and by cost (`list`): a few multi-day sessions usually hold most of it.
4. Propose per pattern the cheapest fix: a project rule (`CLAUDE.md`), a script (no model cost), a hook
   (enforced), or a skill (procedure and lessons). Give counts and name them as approximate.
5. Secrets typed into prompts (tokens, passwords) are reported by date and kind, never quoted; advise
   rotation.
