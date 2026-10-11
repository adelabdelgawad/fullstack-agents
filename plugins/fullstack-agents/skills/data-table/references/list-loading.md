# List loading — rows first, counts beside them, options on demand

The canonical rules for how a server-paginated table loads, counts and refreshes. It overrides any
example in this skill that puts every count and option list in one blocking list response. Read it
before writing, changing or reviewing a list page or the endpoint behind it.

Measured case behind these rules (UCM Leads, 132k rows): one request ran 15 sequential queries — the
page, the total and 13 facet counts — and returned 1.36 MB for 25 rows, 97.5% of it two option lists
(12,406 batches, 7,247 topics). Rows waited ~3 s for counts nobody had asked for, and every live
event re-ran the whole request.

## 1. Three data kinds, three requests

| Data | Request | Blocks rows? | Refreshed by |
|---|---|---|---|
| Rows of the page + `total` | The list endpoint: one page query + one count | — | Page, filter, sort change; relevant live events |
| Facet counts (status, owner, campaign…) | A separate counts request with the same filter | Never | Filter change, manual refresh, an optional slow interval |
| Large option lists (> ~100 options) | Server search over the options, paginated, bounded | Never | Opening the dropdown, typing in its search |

Cheap counts may stay in the list response: a handful of `GROUP BY` buckets over an indexed column
of a small table (`activeCount`/`inactiveCount` on a settings table). Decide by cost, measured on
production-sized data, not by habit: when the counts cost more than the page query, or any facet
can grow without bound, they leave the list response.

## 2. Render rows as soon as they exist

- Server-render the rows; put the counts behind their own boundary (`<Suspense>` streaming a
  server component, or a client fetch started after hydration). The table never waits for them.
- Each facet shows its own loading and error state. A failed counts request leaves the table usable
  and the filters operable without counts.
- During a filter, sort or page change keep the previous rows visible with a pending indicator that
  says they belong to the previous selection; never blank the table.

## 3. Stable, server-side paging

- Pagination, sort and filter run on the server. Select only the columns the page renders.
- Every `ORDER BY` ends with a unique tie-breaker (`…, id`). Without it, rows sharing the sort value
  (bulk imports share `created_at`) repeat or vanish across pages.
- Keep numbered offset pagination until deep pages are measured slow; cursor pagination changes the
  navigation contract and is a product decision.
- Count with `COUNT(*)` when every join is one-to-one on the counted row; `COUNT(DISTINCT pk)` sorts.

## 4. Large option lists are searched, not shipped

- The dropdown opens with a short first page (top by count, or recent), then searches the server.
- Every option the user is authorized to pick stays reachable through search; access scope applies
  to the option query exactly as to the rows.
- Selected values stay visible even when they are outside the current search result.
- Narrowing options to a parent selection (batches of the selected campaigns) is a filter-semantics
  change; make it only when the product says so.

## 5. Refresh rules

- Rows, counts and options have separate cache entries. Their keys include the filter and anything
  that changes what the viewer may see (user, scope).
- A live event refreshes **rows and total only**, coalesced and rate-limited
  ([live-updates.md](../../nextjs/references/live-updates.md)). Filter events by the dataset's scope
  where the event carries it (one batch, one campaign); a cross-scope view accepts every event of
  its tables.
- Counts refresh on filter change and manual refresh; a slow interval is optional and the UI shows
  when they were computed.
- Debounce only free text. Pass the query library's `signal` to the HTTP client so a superseded
  request is cancelled in the browser. That does not stop the database: a dropped backend request
  usually still finishes its query. Reduce the work per request first; a statement timeout bounds
  the rest.

## 6. Prove it with numbers

Before and after, record: endpoint p50/p90 from the access log, payload bytes, query count and DB
time per request, time to visible rows in a browser, refetches per minute of an idle tab during live
traffic. Verify plans with the real parameterised statements (`PREPARE` / `EXPLAIN EXECUTE`, also
with `plan_cache_mode = force_generic_plan`) for a global and a scoped user. Running the old count
queries in parallel shortens one request while multiplying concurrent DB load; it is not a fix.

## 7. Sweep the whole app, never page by page

A slow page reported by a user means the pattern exists elsewhere. Before fixing it, sweep every
surface by contract, not by traffic: an endpoint nobody hit this week is still a page someone opens.

1. **Enumerate every endpoint.** Grep server fetchers (`serverApiFetch`, `*.server.ts`) and client
   fetchers (`api.get`, query `queryFn`s); call each once read-only, and templated paths with one
   real id. Record status, time and bytes.
2. **Write the thresholds into the plan** (default: p50 > 500 ms after three calls, or a response
   > 200 KB). Re-run every offender as the cheapest scope (global admin) *and* a scoped user — scope
   predicates change plans. Anything under both thresholds is left alone, and the plan says so.
3. **Rank by frequency × cost, not one call.** Join the access log (calls per minute) with the
   slow-statement log; sample `pg_stat_activity` (active queries, every 300 ms for 10 minutes, in
   working hours) to catch frequent queries that never cross the slow threshold — dispatch,
   recovery sweeps, polling.
4. **Fix shared sources once.** Several endpoints with the same size usually share one builder.
   Before trimming a payload, read every consumer: a client that aggregates the array would
   silently change its numbers.
5. **Unbounded history is the usual root cause.** A list, facet or sweep that reads every row ever
   written (all batches, all outbox commands) when it needs only the live or recent ones. Scope it
   by a predicate that is provably equivalent (drive from the live set) before reaching for a time
   window; a time window in recovery code can skip a stuck row.

## Review checklist

- [ ] List response = rows + `total` (+ only measured-cheap counts)
- [ ] Counts in their own request and boundary; rows never wait for them
- [ ] No option list ships unbounded; large ones are server-searched with selected values kept
- [ ] `ORDER BY` ends with a unique tie-breaker
- [ ] Live refresh fetches rows + total only; counts on filter change / manual refresh
- [ ] Query `signal` reaches the HTTP client
- [ ] Before/after numbers recorded (§6)
