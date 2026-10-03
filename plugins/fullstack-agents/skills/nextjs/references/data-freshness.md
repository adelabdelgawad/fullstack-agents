# Data freshness — mutation results, refetch, `router.refresh()`, refresh ownership

The canonical rules for how a page's data stays current. Other skills, templates and generators
link here instead of restating them. Read before writing or reviewing a page that lists data,
mutates it, filters it, or receives live updates.

## 1. After a mutation: pick the narrowest update that stays correct

Work down this list and stop at the first option whose correctness you can state.

1. **Apply the server response locally** — only when the response is the complete, authoritative
   row *and* you know its effect on everything the page shows: the current filter, sort,
   pagination, aggregate counts and any related view. Typical safe case: an edit or toggle of a
   field that is not filtered on, sorted on or counted.
2. **Refetch the affected data** (the one list query, the one summary) — when the row's position
   or membership cannot be reconciled safely. Creation is the usual case: the new row may belong
   on another page, sort elsewhere, or fall outside the active filter. So may an edit that changes
   a filtered, sorted or counted field.
3. **`router.refresh()`** — when server-rendered dependencies genuinely need re-rendering (server
   component summaries, layout data, several unrelated server-fetched regions) and no narrower
   refetch covers them. It is legitimate after a mutation. State why in one line at the call site
   or in the plan, and check its fan-out (§3).

Never:
- prepend a created row to the visible page and add 1 to `total` without knowing where it belongs;
  it corrupts sort, page size and pagination (inserting is fine when the response or a
  client-complete dataset tells you its position and the new counts);
- recompute aggregate counts (`activeCount`, facet counts, `total`) from the rows of the current
  page; on a server-paginated table those counts come from the server envelope, so update them
  from a server response or refetch them;
- leave an edited row visible when it no longer matches the active filter, without either
  refetching or deliberately keeping it with a visible "no longer matches" state.

Authorization and authoritative recovery still apply: a mutation that fails with 401/403 follows
the app's auth path, never a silent local update.

## 2. One refresh coordinator per dataset

A dataset (or invalidation domain: a list and the counts derived from it) has exactly one
coordinator that decides when to refetch. Every trigger calls that coordinator; none fetches on
its own.

| Trigger | Role |
|---|---|
| Mutation completion | Asks the coordinator for the update chosen in §1 |
| Realtime event | Asks the coordinator to invalidate (see [live-updates.md](live-updates.md)) |
| Window focus / network reconnect | Opt-in; only when the freshness requirement needs it |
| Stream reconnect resync | Asks once after a reconnect, not per missed event |
| Manual Refresh button | Always allowed |
| Watchdog (no events for N s) | Recovery for missed events; keep it when events can be lost |

- Overlapping triggers never become racing parallel requests. Either coalesce (one in-flight
  request plus at most one trailing request) or supersede (each trigger starts a request and only
  the newest result applies). Coalesce when triggers burst (events, focus); superseding is enough
  for occasional user-driven reloads. Neither may drop a trigger that arrived after the in-flight
  request started — that trigger may carry newer data.
- Background refresh (interval, focus, reconnect) is **opt-in**, enabled per dataset with its
  freshness requirement named. A table-wide "refresh on focus" default is the costly choice.
- Do not poll when a realtime stream already meets the freshness requirement; keep a watchdog or
  reconnect resync as the fallback for missed events.
- Two mechanisms refreshing the same data (SSE handler + focus revalidate + interval) without a
  shared coordinator is a defect even when each is individually bounded.

## 3. `router.refresh()` fan-out

`router.refresh()` re-renders every server component on the route and purges the client router
cache, so every visible prefetching `<Link>` fetches again. Before adding one, know:

- which server fetches the route performs (all of them rerun);
- how many prefetching links are visible (each refetches);
- what can trigger it and how often.

From a timer or an event stream it also needs a floor: a minimum interval between refreshes
(seconds, not milliseconds), everything in between coalesced into one trailing refresh, and no
refresh while `document.visibilityState === "hidden"` (refresh once on return). A trailing
debounce alone does not bound the rate under a continuous stream.

Verify with a request count, not by reading code: the route's RSC and API requests per
mutation/event in a browser trace.

## 4. Stale responses

A list request started for an older filter, page or sort must never replace the result of a newer
one. Tie each response to the request state that produced it (request id, abort the previous
request, or compare the params) and drop superseded results.

## 5. Checklist

- [ ] Each mutation's update choice (§1) is stated, and local application lists why filter, sort,
      pagination and counts stay correct.
- [ ] No created row is inserted into the visible page; no count is recomputed from a page slice.
- [ ] Each dataset names one refresh coordinator and its triggers; background refresh is opt-in
      with a reason.
- [ ] Every `router.refresh()` has a stated server-rendered dependency and a measured fan-out;
      timer/event-driven ones have a floor and a hidden-tab pause.
- [ ] Superseded list responses cannot overwrite newer ones.
