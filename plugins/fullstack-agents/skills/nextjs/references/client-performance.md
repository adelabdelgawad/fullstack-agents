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

`router.refresh()` re-renders every server component on the route and invalidates the client
router cache, so every visible `<Link>` that prefetches fetches again. When to use it, how to
bound it, and the narrower alternatives (apply the response, refetch one query) are in
[data-freshness.md](data-freshness.md) — the canonical rules. The latency-specific points:

- A refresh driven by a timer or event stream without a minimum interval (seconds) and a
  hidden-tab pause is a storm source. Background tabs of the same site can share a renderer
  process, so a hidden tab's refresh loop freezes the tab the user is looking at.
- On a live list, a targeted refetch of the one query (or a row patch from the event payload)
  costs one request; a route refresh costs every server fetch on the route plus every prefetch.

## 4. Review checklist

- [ ] Every `<Link>` rendered per row/card/list item has `prefetch={false}`.
- [ ] The [data-freshness.md](data-freshness.md) checklist passes for every list, mutation and
      `router.refresh()` the change touches.
- [ ] A latency fix is proven with the same measurement that found it: RSC request count per
      minute from the page, long tasks during the click → rows window, and click → rows time
      under 4× CPU throttling.
