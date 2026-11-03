# React + TypeScript dashboard, 1:1 port served at /next

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| U0 | in_progress | Scaffold Vite React TS, /next route, parity harness | scaffold+route+test committed 845d03a; remaining: parity harness (dashboard/parity/, herdr --session fsatest wrapper, recorded API fixtures in scratchpad) |  |  |  |  |
| U1 | pending | Core: store, API, shell, header, toasts, context menu | depends U0 |  |  |  |  |
| U2 | pending | Agents view: tiles, toolbar, orchestrator wall, feed | depends U1 |  |  |  |  |
| U3 | pending | Detail panel: info, git, log, output dialog | depends U1 |  |  |  |  |
| U4 | pending | Terminals: card terminal, Herdr client, menus and modals | depends U1 |  |  |  |  |
| U5 | pending | History view | depends U1 |  |  |  |  |
| U6 | pending | Parity green, switch / to React, remove old UI | depends U2-U5 |  |  |  |  |
<!-- fsa:tasks:end -->

<!-- fsa:checkpoint:start -->
```json
{
  "approvals": [
    {
      "at": "2026-11-03",
      "clarity": "explicit",
      "kind": "task",
      "quote": "we need to update the dashboard into react",
      "scope": "React port of the dashboard",
      "used": true
    },
    {
      "at": "2026-11-03",
      "clarity": "explicit",
      "kind": "task",
      "quote": "Vite + TS, commit dist (Recommended) / 1:1 port (Recommended) / Side by side, then switch (Recommended)",
      "scope": "build, fidelity and rollout choices",
      "used": true
    },
    {
      "at": "2026-11-03",
      "clarity": "explicit",
      "kind": "task",
      "quote": "use react ts",
      "scope": "TypeScript",
      "used": true
    },
    {
      "at": "2026-11-03",
      "clarity": "explicit",
      "kind": "single-use",
      "quote": "Hot-patch installed copy (Recommended)",
      "scope": "copy fad6479 dashboard.html into installed 3.78.2 cache",
      "used": true
    }
  ],
  "blockers": [],
  "constraints": [
    "AGENTS.md: commit on main, linear history; land branch react-dashboard by rebase + fast-forward",
    "commit with -c user.name='Adel Abd Elgawad' -c user.email=tech.ade87@gmail.com; this account cannot push",
    "every brief states the one-line comment rule from ~/.claude/CLAUDE.md",
    "implementer fence allows exact file paths only; set FSA_MAX_ALLOWED_PATHS per dispatch",
    "never attach a scratch dashboard to the live herdr default session: PATH wrapper running herdr --session fsatest",
    "regenerate plugins/fullstack-agents-codex/inventory.json with integrations/codex/scripts/build.py in the worktree at release"
  ],
  "decisions": [
    {
      "id": "D1",
      "source": "docs/REACT_DASHBOARD.md",
      "text": "Source at repo-root dashboard/, dist at scripts/lib/dashboard-react/ with fixed names app.js/app.css, base /next/"
    },
    {
      "id": "D2",
      "source": "docs/REACT_DASHBOARD.md",
      "text": "xterm from vendored /static/xterm globals; @xterm packages types-only"
    },
    {
      "id": "D3",
      "source": "docs/REACT_DASHBOARD.md",
      "text": "Units U0 lead scaffold+harness, U1 core (+typed stubs for U2-U5 files), then U2 agents, U3 panel, U4 terminal, U5 history in parallel, U6 parity+switch"
    }
  ],
  "done": [
    {
      "evidence": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/978905e0-a5f6-4f3f-af8b-b26011a41634/scratchpad/logs/browser.log",
      "text": "Drag-copy fix committed on local main as fad6479 (release 3.78.3), not pushed; hot-patched into the installed 3.78.2 dashboard.html, live on :8766"
    },
    {
      "evidence": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/978905e0-a5f6-4f3f-af8b-b26011a41634/scratchpad/logs/u0-web.log",
      "text": "U0 scaffold committed 845d03a on branch react-dashboard in worktree /home/ashadmin/workspace/fullstack-agents-react"
    }
  ],
  "evidence": [
    "/home/ashadmin/workspace/fullstack-agents-react/docs/REACT_DASHBOARD.md",
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/978905e0-a5f6-4f3f-af8b-b26011a41634/scratchpad/logs"
  ],
  "goal": "Port the agent dashboard (dashboard.html, fleet.js, orchestrators.js, fleet.css) 1:1 to React 18 + TypeScript with Vite; source dashboard/, dist committed at plugins/fullstack-agents/scripts/lib/dashboard-react/, served at /next beside the old UI; switch / in U6.",
  "identity": {
    "branch": "react-dashboard",
    "checkout": "/home/ashadmin/workspace/fullstack-agents-react",
    "detached": false,
    "head": "845d03a339c8ac4cd47199c43e97f3a62b436fd3",
    "root": "/home/ashadmin/workspace/fullstack-agents-react",
    "schema": 1,
    "session_id": "978905e0-a5f6-4f3f-af8b-b26011a41634",
    "task_id": "react-dashboard",
    "written_at": "2026-11-03T13:08:56.194212Z"
  },
  "next": {
    "action": "U0: build parity harness in dashboard/parity/ (playwright-core already installed at scratchpad/pw with chromium ~/.cache/ms-playwright/chromium-1234; replay recorded /api/** fixtures, fixed clock, seeded fsa-* localStorage, compare normalized outerHTML of header,#main,#panel,#ctx,#out on / vs /next) THEN Write and dispatch the U1 core brief via codex-task.sh implement",
    "owner": "lead"
  },
  "scope": {
    "in": [
      "React TS port of every view, panel, menu, dialog and terminal at 1:1 fidelity",
      "/next route in fsa-dashboard",
      "parity harness",
      "vitest ports of JS logic tests"
    ],
    "out": [
      "redesign",
      "right-click Copy last message in the Herdr tab (user: skip, uses Claude /copy)",
      "pushing to GitHub (no credentials on this account)"
    ]
  },
  "status": "active",
  "verification": [
    {
      "command": "python3 -m unittest tests.dashboard.test_herdr_web",
      "fingerprint": {
        "head": "845d03a339c8ac4cd47199c43e97f3a62b436fd3",
        "status_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      },
      "log": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/978905e0-a5f6-4f3f-af8b-b26011a41634/scratchpad/logs/u0-web.log",
      "paths": [
        "plugins/fullstack-agents/scripts/fsa-dashboard",
        "tests/dashboard/test_herdr_web.py"
      ],
      "result": "pass",
      "run_at": "2026-11-03T13:10:00Z"
    }
  ]
}
```
<!-- fsa:checkpoint:end -->

## Task log
<!-- fsa:log:start -->
- 2026-11-03T13:06:07Z - init
<!-- fsa:log:end -->
