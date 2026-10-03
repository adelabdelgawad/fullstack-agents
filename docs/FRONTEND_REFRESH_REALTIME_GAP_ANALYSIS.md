# Frontend refresh, realtime and loading — plugin gap analysis

**Status:** resolved in v3.16.0 (this document ships with that release). Kept as the record of why
the rules in `skills/nextjs/references/{data-freshness,live-updates,client-performance}.md` exist. Source baseline: v3.15.0, commit `e2bc21e`; line numbers below
refer to that commit.

## Trigger

An app-wide audit of a production Next.js 16 frontend built with this plugin found avoidable
latency, redundant fetching and realtime fragility:
- whole-route `router.refresh()` after mutations and realtime events (172 call sites);
- table auto-revalidation on by default and stacked with SSE and manual refresh;
- a second unscoped SSE connection per page;
- `EventSource` left `CLOSED` after an upstream outage (still being reproduced in the app at the
  time of writing);
- a 250 ms debounce on multi-select facets;
- large on-demand sheets imported statically.

The app's own code made the final choices. This document records only what the plugin's text
taught, contradicted or left unsaid. Missing guidance does not prove the plugin caused any app
defect.

## Evidence classes

- **Explicit** — plugin text or template code that prescribes the behaviour.
- **Encourages** — text that presents the behaviour as a normal option without its cost.
- **Propagates** — text that tells an agent to copy the codebase's existing pattern, whatever it is.
- **Contradiction** — two plugin texts that disagree.
- **Partial** — guidance existed but left the decisive case open.
- **Missing** — no guidance existed.
- **Not plugin** — the plugin taught the opposite.

## Findings (v3.15.0)

| # | Behaviour | Class | Plugin source (v3.15.0) |
|---|---|---|---|
| 1 | Whole-route refresh after create | Explicit | `agents/generate/nextjs-data-table.md:144,274,441,561,566` ("`router.refresh()` for add operations") |
| 2 | Same, versus "mutation success paths do not call `router.refresh()`" | Contradiction | `skills/nextjs/references/client-performance.md:59` vs the generator above. The reference was loaded only "before diagnosing latency or adding live refresh" (`skills/nextjs/SKILL.md:312`), so generators never read it. |
| 3 | Created row prepended to the visible page and `total + 1` | Explicit | `skills/nextjs/references/simple-fetching-pattern.md:117-133`, `skills/nextjs/references/table-pattern.md:282-300`, `skills/fetch-architecture/examples.md:311-318` |
| 4 | Status counts recomputed from the current page's rows | Explicit; contradicts the server-count rule in `skills/data-table/SKILL.md:171` and `references/faceted-filters.md:30-40` | `skills/data-table/references/table-component-pattern.md:90-97,297-308`, `skills/nextjs/references/table-pattern.md:89-102`, `simple-fetching-pattern.md:105-113`, `agents/generate/nextjs-data-table.md:458-459` |
| 5 | Local splice recommended after delete; `mutate()` flagged as a warning | Explicit | `agents/review/patterns-compliance.md:260-274` |
| 6 | Toggling a filtered and counted field patched in place only | Explicit | Every Strategy A/B template toggle handler |
| 7 | Background refresh presented as a feature (interval + focus + reconnect) | Encourages | `skills/data-table/references/table-component-pattern.md:488`, `skills/nextjs/references/swr-fetching-pattern.md:80-83,209-213` |
| 8 | "This application uses Strategy A exclusively / SWR not used" (copied project state) | Contradiction with live tables | `skills/data-table/SKILL.md:226`, `skills/nextjs/references/data-fetching-strategy.md:110`, `skills/fetch-architecture/SKILL.md:601`, `swr-fetching-pattern.md:3` |
| 9 | Codebase scan copies the existing update pattern | Propagates | `skills/codebase-scanning/SKILL.md:98,123` |
| 10 | Browser stream lifecycle: sharing, reconnect after `CLOSED`, auth vs forbidden, cleanup, echoes | Missing | No `EventSource` or browser-side reconnect guidance anywhere; `websocket` is server-side Python |
| 11 | Optional UI loading by measured cost | Missing | `agents/review/performance.md:115-118` says only "Missing code splitting" |
| 12 | Debounce on discrete facets | Not plugin | `skills/data-table/references/faceted-filters.md:385-394` applies the selection immediately |
| 13 | Search debounce 2000 vs 300 vs 500 ms | Contradiction | `skills/data-table/SKILL.md:32,160,184`, `references/data-table-requirements.md:126`, `references/context-pattern.md:213` |
| 14 | Extractor classifications treated as fact | Partial | `agents/lead/bounded-extractor.md` forbade interpretation but had no marker for inferred values; the lead had no rule for keeping them as hypotheses |
| 15 | Performance review | Missing | `agents/review/performance.md:112-127`: memoization greps, no refresh, stream or control-latency checks |

## Resolution (v3.16.0)

| Change | Where |
|---|---|
| Canonical mutation-update decision, refresh coordinator, `router.refresh()` fan-out, stale responses | `skills/nextjs/references/data-freshness.md` (new) |
| Canonical browser stream lifecycle and mutation-echo handling | `skills/nextjs/references/live-updates.md` (new) |
| Control responsiveness; measured optional-UI loading | `skills/nextjs/references/client-performance.md` §4–5 |
| Templates: no blind inserts, no page-slice counts, revalidation after toggles, creates and deletes, superseded-response guard | `simple-fetching-pattern.md`, `table-pattern.md`, `table-component-pattern.md`, `fetch-architecture/examples.md`, `data-table/examples.md`, `agents/generate/nextjs-data-table.md` |
| Project-specific "exclusively" statements removed | Findings 8 |
| Required reading wired into skills, generators, the lead's skill table, `prompt-scan` (with tests) and the session doctrine | Commits `b2727fc`, `e77552d`, `02b9bf2` |
| Evidence classes; `inferred:` extractor labels; frontend review questions with proportional justification | `agents/lead/*`, `agents/review/*`, `skills/task-flow/SKILL.md`, `commands/validate.md` |

## Validation

Static review, prompt behaviour and agent behaviour are reported separately; none of this proves
how a future agent behaves on an arbitrary task.

**Static checks.**
- Every relative Markdown link and `skills/...` path under `plugins/fullstack-agents` resolves
  (0 broken before and after).
- `hooks/prompt-scan.test.sh` (with four new frontend cases) and `hooks/lib.test.sh` pass.
- A repository-wide search finds no remaining template that prepends a created row, recomputes
  counts from a page slice, debounces a discrete control, or states project-specific "exclusively"
  usage. Search debounce examples are 300 ms.

**Independent audit.** A separate reviewer checked the revision against the rules. It confirmed
the live-update, echo, optional-UI, evidence and reviewer rules (R8–R12) were covered. It also
spot-checked about 20 baseline citations in this document; all matched.

It reported 23 items. All were fixed before release:
- templates that still patched without reloading on edits and bulk updates;
- a `refresh()` that ignored URL state;
- an unreconciled optimistic toggle;
- a loading overlay on background reloads;
- leftover project labels;
- an unnamed SWR preset trigger;
- four over-strict phrasings (absolute "always reload", the absolute row-prefetch ban, the
  first-mount resync skip, and the "fan-out" wording for debounces and imports).

**Scenario plans** — Sonnet, headless, plugin loaded with `--plugin-dir`, run from an empty
directory. Eight explicit planning prompts were used:
- create in a server-paginated, filtered, sorted table;
- an edit that leaves the filter;
- a server-rendered summary;
- a mutation echo plus another user's update;
- stream recovery after an outage, an expired login and forbidden access;
- a stream shared between layout and page;
- a heavy optional form;
- facet debounce.

All eight follow the revised rules and name the legitimate exceptions:
- a row patch when no filtered field changed;
- `router.refresh()` for a server-rendered summary;
- a backend version field proposed separately;
- measuring before deferring.

The v3.15.0 control produced comparably correct plans for the create and recovery prompts. When a
prompt names the problem, the model already reasons well. These runs show the new text is
coherent and followed; they do not show a behaviour change.

**Generation without hints.** "Write the products table component with create, delete and toggle",
run twice per version:

| Version | Toggle under a filter / without one | Stale-response guard | Create/delete |
|---|---|---|---|
| v3.15.0 | reloads under a filter; otherwise adjusts the counts on the client (2/2 runs) | none | reload |
| v3.16.0 | patches the row, then reloads the list (2/2 runs) | yes (2/2 runs) | reload |
