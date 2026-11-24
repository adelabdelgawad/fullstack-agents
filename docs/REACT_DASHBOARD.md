# React dashboard port

The agent dashboard (`plugins/fullstack-agents/scripts/lib/dashboard.html`, `fleet.js`, `orchestrators.js`,
`fleet.css`) is ported 1:1 to React 18 + TypeScript, built with Vite. Nothing is redesigned: every id, class, text,
style, API call, poll interval, localStorage key and keyboard shortcut stays as it is.

## Decisions

| Topic | Decision |
|---|---|
| Source | `dashboard/` at the repository root (outside the plugin, so `node_modules` never ships) |
| Build | `npm run build` = `tsc -b && vite build`; output committed to `plugins/fullstack-agents/scripts/lib/dashboard-react/` as `index.html`, `app.js`, `app.css` (fixed names, no hashes) |
| Serving | `fsa-dashboard` serves the React `index.html` at `/`, `/next` and `/next/` (one token and cookie), assets at `/next/app.js` and `/next/app.css`; `ui_stamp` is the newest mtime of those three files, so open pages reload after an update |
| xterm | Loaded from the existing vendored globals `/static/xterm/*` (5.5.0); `@xterm/xterm@5.5.0` and addons are types-only devDependencies |
| Fonts | Existing `/static/fonts/*` routes |
| CSS | The `<style>` block of `dashboard.html` and `fleet.css` copied verbatim to `dashboard/src/styles/`; global class names, no CSS modules |
| Document classes | `html.wall`, `html.agents-page`, `html.herdr-page`, `html.lock`, `html.split` stay on `document.documentElement`; the app mounts into `<body>` children with the same ids (`header`, `#main`, `#panel`, `#toasts`, `.wall-hint`, `#out`, `#ctx`) |
| String renderers | `ansiHtml`, `mdHtml`, `saidHtml`, `diffHtml` stay string producers rendered with `dangerouslySetInnerHTML` |
| Imperative parts | xterm terminals, the herdr client, scroll keeping and focus restore live in refs and effects that mirror the current functions |
| State | One external store (`useSyncExternalStore`) holding what the globals hold today (`state`, `herdrData`, `view`, `openKey`, `openRun`, `tab2`, `favOnly`, `fleet`, `git`, `out`, context menu, toasts) |
| Tests | `cd dashboard && npx vitest run`; every case of the retired Python UI tests has a vitest case of the same name (see "Source tests ported"); no release gate runs vitest, so run it before every dashboard commit |
| Rollout | Done: side by side at `/next` until the parity harness was green for every state, then `/` switched and the old files, their Python tests and the harness were removed |

## File map and owners

| Unit | Files (under `dashboard/src/`) | Ports (source lines) |
|---|---|---|
| U0 lead | `../package.json`, `../vite.config.ts`, `../tsconfig.json`, `../index.html`, `styles/dashboard.css`, `styles/fleet.css`, `fsa-dashboard` `/next` route, `parity/` harness | `dashboard.html` 11-539 (CSS), 541-578 (body) |
| U1 core | `main.tsx`, `App.tsx`, `store.ts`, `lib/types.ts`, `lib/api.ts`, `lib/format.ts`, `lib/cards.ts`, `lib/markup.ts`, `lib/clipboard.ts`, `components/Header.tsx`, `components/Toasts.tsx`, `components/CardContextMenu.tsx`, typed stubs for every U2-U5 file | `dashboard.html` 580-600, 601-650, 1657-1735, 1742-1808, 2538-2626, 2758-2842; `fleet.js` 1-58, 187-232 |
| U2 agents | `views/AgentsView.tsx`, `views/agents/*.tsx` | `dashboard.html` 1737-1766, 1869-1902; `fleet.js` 59-173; `orchestrators.js` |
| U3 panel | `panel/*.tsx`, `components/OutDialog.tsx` | `dashboard.html` 1809-1868, 1903-2537, 2627-2757 |
| U4 terminal | `terminal/*.ts(x)`, `views/HerdrView.tsx` | `dashboard.html` 651-1656 |
| U5 history | `views/HistoryView.tsx` | `fleet.js` 174-186 |
| Office (new, not a port) | `views/OfficeView.tsx`, `views/office/*`, `styles/office.css` | none: draws `/api/state` sessions as pixel employees on a canvas (no new requests, no model calls); its prompt box posts `{pane, kind: "prompt"}` to `/api/herdr/send`; served at `/next/office` |

A unit edits only its own files. A needed change to another unit's file is reported, never made.

## Linked hosts (nodes)

| Topic | Decision |
|---|---|
| Registry | `~/.config/fullstack-agents/nodes.json` (`$XDG_CONFIG_HOME` honoured, `FSA_NODES_FILE` overrides), written atomically with mode 0600; `plugins/fullstack-agents/scripts/lib/nodes.py` owns it |
| Routes | `GET/POST /api/nodes` (list without tokens / add `{url, label?}`: the linked dashboard's full URL, parsed into host, port and `t=` token, then probed at `/api/herdr`), `POST /api/nodes/remove`, `GET /api/fs/dirs?path=&hidden=` (folder picker, whole filesystem, at most 500 entries) |
| Proxy | `/api/node/<id>/api/...` forwards the same call to the linked dashboard: strips `t=`, sends the stored token as the `fsa_t` cookie, streams SSE (`/api/herdr/live`) and tunnels WebSockets with the remote Host/Origin (at most 8 tunnels). The token never reaches the browser |
| UI | `store.node` is the focused host (`""` = this host); `lib/api.ts` `nodeUrl()`/`wsUrl()` prefix every call, and a vitest case fails on any raw `/api` fetch outside them. `components/Hosts.tsx` holds the picker and the hosts dialog, `terminal/NewSession.tsx` the host → workspace → folder flow, `OfficeView.tsx` one `OfficeBuilding` per host; the header status names the focused host |
| Transport | Plain HTTP between dashboards: link hosts only on a trusted network or through an SSH tunnel or VPN. A new workspace must be an existing folder; the picker does not create folders |

## Module contract (fixed by U1, consumed by U2-U5)

| Module | Exports | Notes |
|---|---|---|
| `main.tsx` | — | imports both CSS files, `createRoot(document.body).render(<App/>)`: `header` must stay a direct child of `body` (`fleet.css` uses `body > header`) |
| `App.tsx` | `App` | renders, in order: `<Header/>`, `<main id="main">` holding the active view, `<Panel/>`, `<Toasts/>`, `<div class="wall-hint">`, `<OutDialog/>`, `<CardContextMenu/>`, `<HerdrOverlay/>`; owns the `html` classes `wall`, `agents-page`, `herdr-page`, the Escape listener (2830) and the wall keys (`fleet.js` 227-232); the overlay listeners (1671-1680) belong to `HerdrOverlay`, and visibility/pagehide/pageshow handling to the owning units' effects |
| `store.ts` | `store` (`get`, `set(patch or fn)`, `subscribe`), `useStore(selector)`, actions `load`, `loadHerdr(force?)`, `setView`, `setFavOnly`, `setWall`, `setFleet(patch)`, `openCard(key, keepTab?)`, `closePanel`, `toast(html, tone, target?, session?)`, `dismissToast(id)`, `openCtx(cardEl, x, y)`, `closeCtx`, `toggleFavourite(key)`, `onStateLoaded(fn)` | state: `state`, `herdrData`, `view`, `favOnly`, `wall`, `fleet` {filter, sort, text, feed, tilesHidden, tpm}, `openKey`, `openRun`, `tab2`, `offline`, `toasts`, `ctx`; polling every 4000 ms starts in `App`; `onStateLoaded` lets U2 keep its tokens-per-minute samples (`noteTpm`, `noteCardTpm`) on every load |
| `lib/types.ts` | `DashState`, `Card`, `Session`, `Run`, `HerdrState`, `HerdrPane`, … | typed from the fields the old UI reads; unknown extras stay optional |
| `lib/format.ts` | `esc`, `ago`, `chip`, `kb`, `fmtTokens`, `fmtCost`, `modelFamily`, `modelShort` | pure |
| `lib/cards.ts` | `favKeys`, `gitBadge`, `rank`, `needsHuman`, `stageOf`, `STAGES`, `QUIET`, `FLAG_TEXT`, `STAGE_LABEL`, `soleSid`, `worktreesOf`, `cardOfSession`, `sessionOf`, `isStale`, `isRunning`, `fleetMatches`, `fleetCompare` | pure, take state as an argument where the old code read a global |
| `lib/markup.ts` | `ansiHtml`, `mdInline`, `mdCells`, `mdHtml`, `saidHtml`, `saidText`, `lastPara`, `toolLine`, `questionLine` | string producers, byte-identical to the old ones |
| `lib/clipboard.ts` | `copyText`, `writeClipboard` | |
| Stubs U1 creates | `views/AgentsView.tsx` (U2), `views/HistoryView.tsx` (U5), `views/HerdrView.tsx` (U4), `panel/Panel.tsx` (U3), `components/OutDialog.tsx` (U3), `terminal/CardTerminal.tsx` (U4), `terminal/HerdrOverlay.tsx` (U4) | each a typed export returning the old UI's static markup or `null`; the owning unit replaces the body, never the signature; cross-unit calls are stubbed now: `openAgent(sid, id, view?)` and `isOutOpen()` in `OutDialog.tsx`, `openRunLog(cardKey, runId)` in `Panel.tsx` |

`terminal/HerdrOverlay.tsx` exports `HerdrOverlay` plus `openNewSession(anchor)`, `openHerdrConfirm(title, text, action,
params, returnFocus, opts)`, `openHerdrContextMenu(kind, item, x, y, anchor)`, `closeHerdrOverlay(restoreFocus?)` and
`herdrAction(action, params?, ownerRoot?)`. `CardTerminal` takes `{card}` and ports `matchedCardPane` and
`paintCardTerminal` (2372-2423); U3 renders it inside `#card-terminal`. Unit-private state (git panel, output dialog,
terminals) lives in the owning unit's files, not in `store.ts`.

## Parity harness (retired)

`dashboard/parity/` replayed recorded API responses into `/` (old UI) and `/next` and compared the normalized DOM of
`header`, `#main`, `#panel`, `#ctx` and `#out` per named state. Its last run before the switch was green for every
state (U1 9, U2 34, U3 17, U4 11, U5 4, context menu 3). With the old UI gone it has nothing to compare and was deleted;
`git show <switch commit>^:dashboard/parity/` restores it.

## Known divergence from the old UI

Switching view while the detail panel is open inline (inside `#orc-detail`): the old UI's history and Herdr renders
replaced `#main` with the panel still inside it, so `#panel` was destroyed and every later panel action threw
`Cannot read properties of null (reading 'classList')`. The React UI moves the panel back to `<body>` and closes it, as
the old `closePanel()` intended.

## Source tests ported

| Retired Python test | vitest file |
|---|---|
| `tests/dashboard/test_information_ui.py` `InformationUiTests` | `dashboard/src/panel/info.test.tsx` |
| `tests/dashboard/test_fleet_ui.py` | `dashboard/src/views/agents/fleet.test.tsx` (`scripts_share_no_top_level_names` dropped: ES modules share no globals) |
| `tests/dashboard/test_terminal_scroll.py` | `dashboard/src/terminal/terminal.test.ts` |
| `tests/dashboard/test_herdr_client_ui.py` | `dashboard/src/terminal/herdr.test.ts` |

`SessionStateDashboardTests` in `tests/dashboard/test_information_ui.py` tests Python and stays.
