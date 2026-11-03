# React + TypeScript dashboard, 1:1 port served at /next

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| U0 | done | Scaffold Vite React TS, /next route, parity harness | scaffold 845d03a; parity harness dashboard/parity (serve.sh, run.mjs record\|compare, states.mjs); / vs / green 48/48; fixtures in session scratchpad |  |  |  |  |
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
- 2026-11-03T13:19:04Z U0 accept reason="" invalidated=""
- 2026-11-03T13:19:08Z U0 check_start check="C1" run="6ea9f895143cdd59872f4350319a0f0a"
- 2026-11-03T13:19:17Z U0 check_finish check="C1" run="6ea9f895143cdd59872f4350319a0f0a" result="pass" executor="tool" reason=""
- 2026-11-03T13:19:17Z U0 check_start check="C2" run="4965d9fb7773fd44e7478ee8ca89a12c"
- 2026-11-03T13:19:20Z U0 check_finish check="C2" run="4965d9fb7773fd44e7478ee8ca89a12c" result="pass" executor="tool" reason=""
- 2026-11-03T13:19:20Z U0 check_start check="C3" run="f76d65ded73d0f871341e9c52135b17b"
- 2026-11-03T13:19:55Z U0 check_finish check="C3" run="f76d65ded73d0f871341e9c52135b17b" result="pass" executor="tool" reason=""
- 2026-11-03T13:20:03Z U0 check_start check="R1" run="0d77b4f761084adbea39a0467761cb6d"
- 2026-11-03T13:20:03Z U0 check_finish check="R1" run="0d77b4f761084adbea39a0467761cb6d" result="pass" executor="attested" reason=""
- 2026-11-03T13:20:08Z U0 status from="in_progress" to="done" reason=""
- 2026-11-03T13:20:08Z U0 done_gate accepted="C1, C2, C3, R1"
<!-- fsa:log:end -->

<!-- fsa:evidence:start -->
```json
{
  "baselines": {},
  "deliverables": {
    "U0": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "python3 -m unittest tests.dashboard.test_herdr_web",
          "cwd": ".",
          "definition_digest": "8bee8fc3e7245deebec29b194057e672802db25fdef5752dde5c23e643b0e399",
          "expect": {
            "patterns": [
              "OK"
            ],
            "reject": [
              "FAILED"
            ]
          },
          "method": "command"
        },
        "C2": {
          "command": "npm run -s typecheck && echo typecheck-ok",
          "cwd": "dashboard",
          "definition_digest": "ed513a4003d1fd32fa7f73af3da7b6e4699e5abe8c5df125e5dacae38926ae94",
          "expect": {
            "patterns": [
              "typecheck-ok"
            ],
            "reject": []
          },
          "method": "command"
        },
        "C3": {
          "command": "node parity/run.mjs compare --fixtures /tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/fixtures --right / --out /tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/parity-selfcheck",
          "cwd": "dashboard",
          "definition_digest": "23c7e8c89635bd80035a15001ffbd0ae0c8c00e404efb18b7388472b7fd2e63a",
          "expect": {
            "patterns": [
              "GREEN: (\\d+)/\\1 equal"
            ],
            "reject": [
              "RED",
              "ERROR"
            ]
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "1d651262f5bf6511bfd0306399cca0e1009a6aa5c6f4d470ef563a582d3a4c13",
          "method": "review"
        }
      },
      "completed": {
        "at": "2026-11-03T13:20:08.922213Z",
        "with": {
          "C1": "pass",
          "C2": "pass",
          "C3": "pass",
          "R1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "AC1",
          "text": "/next, /next/app.js and /next/app.css are served behind the token"
        },
        {
          "checks": [
            "C2"
          ],
          "id": "AC2",
          "text": "TypeScript scaffold type-checks"
        },
        {
          "checks": [
            "C3",
            "R1"
          ],
          "id": "AC3",
          "text": "Parity harness is deterministic: / vs / green on every state, no API pass-through"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "8bee8fc3e7245deebec29b194057e672802db25fdef5752dde5c23e643b0e399",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/66bc761938bc58fb/U0-C1-20261103T131908Z.log",
              "sha256": "28d884c8c29a1580199d6a65f1713ae9d4b3d7ec55e6843140453a962f49854a"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-03T13:19:17.401925Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:19:08.721076Z",
          "state_after": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          },
          "state_before": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          }
        },
        "C2": {
          "definition_digest": "ed513a4003d1fd32fa7f73af3da7b6e4699e5abe8c5df125e5dacae38926ae94",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/66bc761938bc58fb/U0-C2-20261103T131917Z.log",
              "sha256": "f49bcff8482b2b6c648f036f1a0e49773ede65a11581bd8732f2ff8756ddade3"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-03T13:19:20.230059Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:19:17.619255Z",
          "state_after": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          },
          "state_before": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          }
        },
        "C3": {
          "definition_digest": "23c7e8c89635bd80035a15001ffbd0ae0c8c00e404efb18b7388472b7fd2e63a",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/66bc761938bc58fb/U0-C3-20261103T131920Z.log",
              "sha256": "0ac9101a07c00505209514492568041684090517bd083de2bf8e83144f6402f0"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-03T13:19:55.998105Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:19:20.402611Z",
          "state_after": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          },
          "state_before": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          }
        },
        "R1": {
          "definition_digest": "1d651262f5bf6511bfd0306399cca0e1009a6aa5c6f4d470ef563a582d3a4c13",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/u0-review.md",
              "sha256": "3d3b60e049a7509f021e5bd67642699f7b3d1fa47cae744d6395baac1c87b818"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-03T13:20:03.177520Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:20:03.082882Z",
          "state_after": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          },
          "state_before": {
            "digest": "3fe193105e0bdfbeea72f8d362953df4723d5b954da8c8cfccd0dc90725399b6",
            "files": 18,
            "head": "a63380d948e8711ff406df2b478e936caadc48a5"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/scripts/lib/dashboard.html",
          "plugins/fullstack-agents/scripts/lib/fleet.js",
          "plugins/fullstack-agents/scripts/lib/orchestrators.js",
          "plugins/fullstack-agents/scripts/lib/fleet.css"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/parity/",
          "dashboard/package.json",
          "dashboard/package-lock.json",
          "dashboard/vite.config.ts",
          "dashboard/tsconfig.json",
          "dashboard/index.html",
          "dashboard/src/",
          "plugins/fullstack-agents/scripts/fsa-dashboard",
          "tests/dashboard/test_herdr_web.py"
        ],
        "rationale": "scaffold, /next route and parity harness; the harness drives the old UI files"
      },
      "spec_at": "2026-11-03T13:19:04.463323Z"
    }
  },
  "runs": {},
  "schema": 1
}
```
<!-- fsa:evidence:end -->

## Ownership log
- 2026-11-03T13:09:18.581136Z adopted by 34f94a84-a134-4113-8eba-235795412266 from 978905e0-a5f6-4f3f-af8b-b26011a41634 (free)
