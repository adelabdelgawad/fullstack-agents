# Client performance — slow navigation, long skeletons, frozen pages

Read this before diagnosing any "the page shows a skeleton for N seconds", "navigation is slow" or
"the UI freezes" report, and before adding `<Link>`, `router.refresh()` or live updates to a page.

## 1. Measure first: server time vs browser time

A skeleton that lasts seconds is either a slow server response or a busy browser. Split them
before any hypothesis:

1. **Server time.** Read the proxy access log for the page's RSC request (`GET /path?_rsc=…`).
   Log `$request_time` (nginx `rt=`); it covers the full response. Milliseconds here clears the
   server, the backend call and the database.
2. **Browser time.** In the same log, find the JS chunk requests (`/_next/static/chunks/*.js`)
   that follow the navigation. A gap of seconds between the RSC response and the chunk request —
   with each chunk served in milliseconds — means the browser's main thread was busy. Chunk loads
   are started by JavaScript after the RSC payload is parsed on the main thread.
3. **Referer check.** Chunk requests still carrying the *previous* page as Referer mean the
   navigation had not committed yet: the main thread was blocked.
4. **Reproduce in a real browser.** Playwright/Chromium with a valid session cookie. Record
   `PerformanceObserver({ type: "longtask" })`, a CDP CPU profile, and per-request timestamps.
   Navigate by clicking the real link (not `page.goto`). Run it with
   `Emulation.setCPUThrottlingRate` 4 to match an average office PC. Compare a busy starting page
   with a quiet one. A clean fast run proves the route is fine and the cost lives in what the
   session was doing before the click.

Count RSC requests per originating page (Referer) over 24 h. A page that makes thousands is a
storm source, whatever page the user complained about.

## 2. `<Link>` prefetch in repeated UI

`next/link` prefetches every link that enters the viewport. In a table row, a card grid or a
live list that means one RSC request per row, per mount.

- **Links inside table cells, list rows and cards: `prefetch={false}`.** Prefetch is for a few
  high-intent navigation targets (sidebar, primary tabs), never for N data rows.
- A cell that remounts (new row identity, column rebuild, `router.refresh()`) prefetches again.
  Remount plus prefetch turns every refresh into N requests plus N RSC parses on the main thread.
- A link whose `href` embeds a per-row value (`?dial=<phone>`, `?campaignIds=<id>`) never hits a
  shared cache entry. Each row is a distinct prefetch.
- A sidebar group that expands with 10–20 links fires a prefetch burst at once. That is
  acceptable one-off; it is not acceptable on a timer.

## 3. `router.refresh()` is a whole-page repaint and a cache purge

`router.refresh()` re-renders every server component on the route. It also invalidates the
client router cache, so every visible `<Link>` that prefetches fetches again.

- **Never drive `router.refresh()` from a live event stream without a floor.** A trailing
  debounce alone does not bound the rate: under a continuous event stream it fires once per
  debounce gap, indefinitely. Enforce a minimum interval between refreshes (seconds, not
  milliseconds) and coalesce everything in between into one trailing refresh.
- **Pause while hidden.** `document.visibilityState === "hidden"` → do not refresh. Remember that
  an event arrived, and refresh once on `visibilitychange` back to visible. Background tabs of
  the same site can share a renderer process, so a hidden tab's refresh loop freezes the tab the
  user is looking at.
- Prefer a targeted client refetch (TanStack Query / SWR invalidation of the one list) or a row
  patch from the event payload over a whole-route refresh when the page is a live list.
- Mutation success paths patch the row from the server response; they do not call
  `router.refresh()` (see the data-table skill).

## 4. Review checklist

- [ ] Every `<Link>` rendered per row/card/list item has `prefetch={false}`.
- [ ] No `router.refresh()` reachable from a timer or event stream without a minimum interval and
      a hidden-tab pause.
- [ ] Live pages refetch the one query they display, not the whole route, where the data layer
      allows it.
- [ ] A latency fix is proven with the same measurement that found it: RSC request count per
      minute from the page, long tasks during the click → rows window, and click → rows time
      under 4× CPU throttling.
