# React dashboard port

The agent dashboard (`plugins/fullstack-agents/scripts/lib/dashboard.html`, `fleet.js`, `orchestrators.js`,
`fleet.css`) is ported 1:1 to React 18 + TypeScript, built with Vite. Nothing is redesigned: every id, class, text,
style, API call, poll interval, localStorage key and keyboard shortcut stays as it is.

## Decisions

| Topic | Decision |
|---|---|
| Source | `dashboard/` at the repository root (outside the plugin, so `node_modules` never ships) |
| Build | `npm run build` = `tsc -b && vite build`; output committed to `plugins/fullstack-agents/scripts/lib/dashboard-react/` as `index.html`, `app.js`, `app.css` (fixed names, no hashes) |
| Serving | `fsa-dashboard` serves the React UI at `/next` (same token and cookie as `/`), assets at `/next/app.js` and `/next/app.css`; the old UI stays at `/` until the switch |
| xterm | Loaded from the existing vendored globals `/static/xterm/*` (5.5.0); `@xterm/xterm@5.5.0` and addons are types-only devDependencies |
| Fonts | Existing `/static/fonts/*` routes |
| CSS | The `<style>` block of `dashboard.html` and `fleet.css` copied verbatim to `dashboard/src/styles/`; global class names, no CSS modules |
| Document classes | `html.wall`, `html.agents-page`, `html.herdr-page`, `html.lock`, `html.split` stay on `document.documentElement`; the app mounts into `<body>` children with the same ids (`header`, `#main`, `#panel`, `#toasts`, `.wall-hint`, `#out`, `#ctx`) |
| String renderers | `ansiHtml`, `mdHtml`, `saidHtml`, `diffHtml` stay string producers rendered with `dangerouslySetInnerHTML` |
| Imperative parts | xterm terminals, the herdr client, scroll keeping and focus restore live in refs and effects that mirror the current functions |
| State | One external store (`useSyncExternalStore`) holding what the globals hold today (`state`, `herdrData`, `view`, `openKey`, `openRun`, `tab2`, `favOnly`, `fleet`, `git`, `out`, context menu, toasts) |
| Tests | Pure logic ported to vitest next to its module; the Python tests keep guarding the old UI until the switch |
| Rollout | Side by side at `/next`; switch `/` once the parity harness is green, then delete the old files and their source-regex tests |

## File map and owners

| Unit | Files (under `dashboard/src/`) | Ports (source lines) |
|---|---|---|
| U0 lead | `../package.json`, `../vite.config.ts`, `../tsconfig.json`, `../index.html`, `styles/dashboard.css`, `styles/fleet.css`, `fsa-dashboard` `/next` route, `parity/` harness | `dashboard.html` 11-539 (CSS), 541-578 (body) |
| U1 core | `main.tsx`, `App.tsx`, `store.ts`, `lib/types.ts`, `lib/api.ts`, `lib/format.ts`, `lib/cards.ts`, `lib/markup.ts`, `lib/clipboard.ts`, `components/Header.tsx`, `components/Toasts.tsx`, `components/CardContextMenu.tsx`, typed stubs for every U2-U5 file | `dashboard.html` 580-600, 601-650, 1657-1735, 1742-1808, 2538-2626, 2758-2842; `fleet.js` 1-58, 187-232 |
| U2 agents | `views/AgentsView.tsx`, `views/agents/*.tsx` | `dashboard.html` 1737-1766, 1869-1902; `fleet.js` 59-173; `orchestrators.js` |
| U3 panel | `panel/*.tsx`, `components/OutDialog.tsx` | `dashboard.html` 1809-1868, 1903-2537, 2627-2757 |
| U4 terminal | `terminal/*.ts(x)`, `views/HerdrView.tsx` | `dashboard.html` 651-1656 |
| U5 history | `views/HistoryView.tsx` | `fleet.js` 174-186 |

A unit edits only its own files. A needed change to another unit's file is reported, never made.

## Parity harness

`dashboard/parity/` (Playwright, run by the lead) loads `/` and `/next` from one scratch dashboard with:

- recorded API responses replayed through `page.route('/api/**')`;
- a fixed clock (`page.clock.setFixedTime`) and identical seeded `fsa-*` localStorage;
- a `herdr` wrapper first on `PATH` that runs `herdr --session fsatest`, so no scratch dashboard touches a live session.

For each named state (view, open card, panel tab, open menu or dialog, filter, wall mode) it compares the normalized
`outerHTML` of `header`, `#main`, `#panel`, `#ctx` and `#out` (attributes sorted, whitespace-only text dropped). A unit
is accepted when its states are DOM-equal and its tests pass.

Normalization also compares `html` classes and `document.title`, rewrites `style` from `el.style.cssText`, sorts class
tokens, drops the old UI's render caches (`data-h`, `data-sig`), and replaces the inside of `.terminal` and
`.herdr-client` with `[opaque]` (xterm is checked by U4's own tests). `WebSocket` and `EventSource` are inert stubs.

| Step | Command (from `dashboard/`) |
|---|---|
| Scratch server | `parity/serve.sh 18766` (127.0.0.1, herdr wrapper on `PATH` bound to session `fsatest`) |
| Record fixtures | `PARITY_LIVE_TOKEN=<live dashboard token> node parity/run.mjs record --fixtures <scratch dir>`; drives `/` through every state, saves GET responses, takes `/api/herdr*` read-only from the live dashboard (`--live`, default `http://127.0.0.1:8766`) |
| Compare | `node parity/run.mjs compare --fixtures <scratch dir> [--unit U2] [--state panel-git]`; exit 0 only when every root is equal and no harness error |
| Self-check | `--right /` must be green; a red self-check means the harness, not the port, is wrong |

Fixtures hold real session data: keep them in a scratch directory, never in the repository. A request with no fixture is
answered 404 and reported as a harness error; nothing passes through to a server. States are data in
`parity/states.mjs` (`name`, owning `unit`, `seed`, `steps`, `roots`); a unit adds the states it needs.

## Source tests to port

| Python test (old UI) | React owner |
|---|---|
| `tests/dashboard/test_herdr_client_ui.py` | U4 (`terminal/osc52.test.ts`), U1 (`lib/clipboard.test.ts`) |
| `tests/dashboard/test_terminal_scroll.py` | U4 |
| `tests/dashboard/test_fleet_ui.py` | U1 / U2 |
| `tests/dashboard/test_information_ui.py` | U3 |
