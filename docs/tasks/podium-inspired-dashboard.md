# Podium-inspired dashboard upgrades

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | done | Usage module: tokens, context fill, compactions, cost, redaction (lib/usage.py) | Real transcripts: 7MB first scan 0.1s, rescan 0.1ms; redaction sample verified |  |  |  |
| T02 | done | Server: attach usage to sessions + summary totals + activity feed + failure cause + history | Totals/history/feed/cause/redaction in state; warm build 0.3s same as before, first build +0.45s | lead | Wiring usage into server state |  |
| T03 | done | UI: summary tiles, context bar/blowout badge, cost, worker squares, legend | Tiles, context bar, N× badge, cost, worker squares, legend; screenshots v3-*.png |  |  |  |
| T04 | done | UI: activity feed pane, filter chips + sort, wall mode (w), theme toggle, history view | Feed, filters+sort, wall mode (w/Esc), Light/Dark/System, History tab; 390px no h-scroll |  |  |  |
| T05 | done | Lead behaviour: context budget, cost in done report, stale vs waiting (skills/agent text) | fsa-usage CLI + lead Context and cost budget section; dashboard.md documents views |  |  |  |
| T06 | done | Tests + screenshots + release | Released as 3.60.0 |  |  |  |
| T07 | done | Orchestrator layout: session sidebar, orchestrator card grid, docked details (metrics, plan, workers, activity) | 11 test files green (dash-tests-4.log); screenshots v5-*.png |  |  |  |
| T08 | done | Plan usage tiles (Claude endpoint, Codex rate limits), navbar controls, wall switch, app-shell panels | dash-tests-9 green; screenshots v11/v14 |  |  |  |
| T09 | in_progress | Mouse-wheel scrolling inside app-shell panels | Reproduced: wheel over cards/feed/details does not scroll them; injected fixed scroller does; cause not yet found |  |  |  |
<!-- fsa:tasks:end -->
