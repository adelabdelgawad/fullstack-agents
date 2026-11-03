# React + TypeScript dashboard, 1:1 port served at /next

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| U0 | done | Scaffold Vite React TS, /next route, parity harness | scaffold 845d03a; parity harness dashboard/parity (serve.sh, run.mjs record\|compare, states.mjs); / vs / green 48/48; fixtures in session scratchpad |  |  |  |  |
| U1 | done | Core: store, API, shell, header, toasts, context menu | lead audit + repairs; build, 25 vitest, shell parity 6/6 green; ctx-menu state re-checked once U2 renders cards |  |  |  |  |
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
    },
    {
      "evidence": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/logs/parity-self4.log",
      "text": "U0 parity harness committed af23ae4 + states e705b2d; contract 77dd272 in docs/REACT_DASHBOARD.md 'Module contract'; / vs / green 75/75"
    },
    {
      "evidence": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/parity-u1-shell.log",
      "text": "U1 audited, repaired by lead and committed 151132d + 3ded64c; ledger checks BUILD/C1/C2/R1/R2 pass; shell parity 6/6"
    }
  ],
  "evidence": [
    "/home/ashadmin/workspace/fullstack-agents-react/docs/REACT_DASHBOARD.md",
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/978905e0-a5f6-4f3f-af8b-b26011a41634/scratchpad/logs",
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/fixtures/fixtures.json",
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/briefs/u1.md",
    "/home/ashadmin/.codex/fsa-runs/implement-20261103-132435-541185.last.txt",
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/handoff-next.md",
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/u1-review.md"
  ],
  "goal": "Port the agent dashboard (dashboard.html, fleet.js, orchestrators.js, fleet.css) 1:1 to React 18 + TypeScript with Vite; source dashboard/, dist committed at plugins/fullstack-agents/scripts/lib/dashboard-react/, served at /next beside the old UI; switch / in U6.",
  "identity": {
    "branch": "react-dashboard",
    "checkout": "/home/ashadmin/workspace/fullstack-agents-react",
    "detached": false,
    "head": "3ded64c8198d4d7460a05332d2481650d9dfc2d2",
    "root": "/home/ashadmin/workspace/fullstack-agents-react",
    "schema": 1,
    "session_id": "74648219-b630-4dfc-9bf2-9f49d6dfc6fc",
    "task_id": "react-dashboard",
    "written_at": "2026-11-03T13:46:23.392905Z"
  },
  "next": {
    "action": "write U2/U3/U4 briefs and dispatch in parallel, port U5 directly; full notes in /tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/handoff-next.md",
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
- 2026-11-03T13:23:00Z U1 accept reason="" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/briefs/u1.md"
- 2026-11-03T13:23:45Z U1 accept reason="PLAN line reformatted for the dispatcher; criteria unchanged" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/briefs/u1.md"
- 2026-11-03T13:24:31Z U1 accept reason="blank line ends the path list; criteria unchanged" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/34f94a84-a134-4113-8eba-235795412266/scratchpad/briefs/u1.md"
- 2026-11-03T13:24:35Z U1 status from="pending" to="in_progress" reason=""
- 2026-11-03T13:28:54Z B1 block kind="worker" rows="U2,U3,U4,U5,U6"
- 2026-11-03T13:39:00Z B1 resolve kind="worker" reason="U1 run ended (scope_violation = lead's own parity edits only)"
- 2026-11-03T13:39:00Z U2 status from="blocked" to="pending" reason="blocker B1 resolved"
- 2026-11-03T13:39:00Z U3 status from="blocked" to="pending" reason="blocker B1 resolved"
- 2026-11-03T13:39:00Z U4 status from="blocked" to="pending" reason="blocker B1 resolved"
- 2026-11-03T13:39:00Z U5 status from="blocked" to="pending" reason="blocker B1 resolved"
- 2026-11-03T13:39:00Z U6 status from="blocked" to="pending" reason="blocker B1 resolved"
- 2026-11-03T13:39:00Z U1 status from="in_progress" to="verifying" reason=""
- 2026-11-03T13:43:13Z U1 check_start check="BUILD" run="72fe813d9e7d66b8e163d52707e18394"
- 2026-11-03T13:43:25Z U1 check_finish check="BUILD" run="72fe813d9e7d66b8e163d52707e18394" result="pass" executor="tool" reason=""
- 2026-11-03T13:43:26Z U1 check_start check="C1" run="cc56b5de73ef2a6253119d84cbcddc81"
- 2026-11-03T13:43:32Z U1 check_finish check="C1" run="cc56b5de73ef2a6253119d84cbcddc81" result="pass" executor="tool" reason=""
- 2026-11-03T13:43:32Z U1 check_start check="C2" run="4c42f00a0e22f0e7b254e75e74c3046c"
- 2026-11-03T13:43:39Z U1 check_finish check="C2" run="4c42f00a0e22f0e7b254e75e74c3046c" result="pass" executor="tool" reason=""
- 2026-11-03T13:43:47Z U1 check_start check="R1" run="7df04d227f851abc9520c0584782b5e5"
- 2026-11-03T13:43:48Z U1 check_finish check="R1" run="7df04d227f851abc9520c0584782b5e5" result="pass" executor="attested" reason=""
- 2026-11-03T13:43:48Z U1 check_start check="R2" run="e6090b44b137c55f366703df6a340781"
- 2026-11-03T13:43:48Z U1 check_finish check="R2" run="e6090b44b137c55f366703df6a340781" result="pass" executor="attested" reason=""
- 2026-11-03T13:44:07Z U1 status from="verifying" to="done" reason=""
- 2026-11-03T13:44:07Z U1 done_gate accepted="BUILD, C1, C2, R1, R2"
- 2026-11-03T13:48:49Z U2 accept reason="" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/704b0464-bfd3-4f1b-a591-af0eec8e6151/scratchpad/briefs/u2.md"
- 2026-11-03T13:48:49Z U3 accept reason="" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/704b0464-bfd3-4f1b-a591-af0eec8e6151/scratchpad/briefs/u3.md"
- 2026-11-03T13:48:49Z U4 accept reason="" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/704b0464-bfd3-4f1b-a591-af0eec8e6151/scratchpad/briefs/u4.md"
- 2026-11-03T13:50:41Z U2 accept reason="advisor fixes: tsx test paths, showRunLog exception, shared lib helpers, no second contextmenu handler" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/704b0464-bfd3-4f1b-a591-af0eec8e6151/scratchpad/briefs/u2.md"
- 2026-11-03T13:50:41Z U3 accept reason="advisor fixes: tsx test paths, showRunLog exception, shared lib helpers, no second contextmenu handler" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/704b0464-bfd3-4f1b-a591-af0eec8e6151/scratchpad/briefs/u3.md"
- 2026-11-03T13:50:41Z U4 accept reason="advisor fixes: tsx test paths, showRunLog exception, shared lib helpers, no second contextmenu handler" invalidated="" brief="/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/704b0464-bfd3-4f1b-a591-af0eec8e6151/scratchpad/briefs/u4.md"
<!-- fsa:log:end -->

<!-- fsa:blockers:start -->
```json
{
  "blockers": {
    "B1": {
      "created_at": "2026-11-03T13:28:54.800172Z",
      "kind": "worker",
      "next": "audit U1, then dispatch U2-U4 in parallel and port U5 directly",
      "resolution": {
        "at": "2026-11-03T13:39:00.869120Z",
        "by": "tool",
        "evidence": "/home/ashadmin/.codex/fsa-runs/implement-20261103-132435-541185.result.json: state=scope_violation",
        "reason": "U1 run ended (scope_violation = lead's own parity edits only)"
      },
      "resumes": {
        "U2": "pending",
        "U3": "pending",
        "U4": "pending",
        "U5": "pending",
        "U6": "pending"
      },
      "rows": [
        "U2",
        "U3",
        "U4",
        "U5",
        "U6"
      ],
      "status": "resolved",
      "text": "U1 implementer run implement-20261103-132435-541185 in progress",
      "why": "U2-U5 build on U1's store, libs and stubs; U6 needs U2-U5"
    }
  },
  "schema": 1
}
```
<!-- fsa:blockers:end -->

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
    },
    "U1": {
      "automated_waiver": null,
      "checks": {
        "BUILD": {
          "command": "cd dashboard && npm run -s build && npx vitest run",
          "cwd": ".",
          "definition_digest": "240efb98d2ac82eabf2b1533640743598945d9c712c8a8d07fce77b12af0b6d7",
          "expect": {
            "none": "compile/lint success is silent"
          },
          "method": "command"
        },
        "C1": {
          "command": "npm run -s build",
          "cwd": "dashboard",
          "definition_digest": "c941c01e5a1a1c58dd6b14f5a2dd9bbfa78a725705040934ce2d1ccdaeed8412",
          "expect": {
            "patterns": [
              "built in"
            ],
            "reject": []
          },
          "method": "command"
        },
        "C2": {
          "command": "npx vitest run",
          "cwd": "dashboard",
          "definition_digest": "c124477e51ddd1ce826476643efacf3da6b0ff0f9220d7a5486529e85515e7b2",
          "expect": {
            "patterns": [
              "Tests +[0-9]+ passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "2b78b990a90a7c8d87ce9c0ca3ac62c8e4db6b07ec63a134fb2c1e4fe94818b1",
          "method": "inspection"
        },
        "R2": {
          "definition_digest": "3eced88db8b9bcc815eeb0c0f2e26abe6089513699870d8b519066ea66ca6267",
          "method": "review"
        }
      },
      "completed": {
        "at": "2026-11-03T13:44:07.932094Z",
        "with": {
          "BUILD": "pass",
          "C1": "pass",
          "C2": "pass",
          "R1": "pass",
          "R2": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "1",
          "text": "Type-check and build pass, emitting app.js and app.css"
        },
        {
          "checks": [
            "C2"
          ],
          "id": "2",
          "text": "Library tests pass"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "3",
          "text": "Shell state is DOM-equal to the old UI (header, #ctx, #out, #toasts, html classes, title)"
        },
        {
          "checks": [
            "R2"
          ],
          "id": "4",
          "text": "Every module and stub matches the contract table; no file outside ALLOWED_PATHS"
        },
        {
          "checks": [
            "BUILD"
          ],
          "id": "BUILD",
          "text": "BUILD passes"
        }
      ],
      "kind": "code",
      "results": {
        "BUILD": {
          "definition_digest": "240efb98d2ac82eabf2b1533640743598945d9c712c8a8d07fce77b12af0b6d7",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/u1-BUILD.log",
              "sha256": "3bb4271981a55ba1d47c343ab05601564028eebfa38987fce0ae4d4235fd7a01"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-03T13:43:25.846324Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:43:13.008205Z",
          "state_after": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          },
          "state_before": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          }
        },
        "C1": {
          "definition_digest": "c941c01e5a1a1c58dd6b14f5a2dd9bbfa78a725705040934ce2d1ccdaeed8412",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/u1-C1.log",
              "sha256": "fbf130eff9cc05b19c904670cb62bb4bc0215273eb278417dc1ecf33f90057f1"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-03T13:43:32.632100Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:43:26.165313Z",
          "state_after": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          },
          "state_before": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          }
        },
        "C2": {
          "definition_digest": "c124477e51ddd1ce826476643efacf3da6b0ff0f9220d7a5486529e85515e7b2",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/u1-C2.log",
              "sha256": "c5487e7bb6170b5a47cb06d194efa21a6622c0c7896afcc7c47cd9df75780837"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-03T13:43:39.023558Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:43:32.755831Z",
          "state_after": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          },
          "state_before": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          }
        },
        "R1": {
          "definition_digest": "2b78b990a90a7c8d87ce9c0ca3ac62c8e4db6b07ec63a134fb2c1e4fe94818b1",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/parity-u1-shell.log",
              "sha256": "78171333f6f4766cdbcf8d8e2a5dac98ff527f15976b883e56c9dc6cdf815445"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-03T13:43:48.072477Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:43:47.881184Z",
          "state_after": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          },
          "state_before": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          }
        },
        "R2": {
          "definition_digest": "3eced88db8b9bcc815eeb0c0f2e26abe6089513699870d8b519066ea66ca6267",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/74648219-b630-4dfc-9bf2-9f49d6dfc6fc/scratchpad/logs/u1-review.md",
              "sha256": "5d05a76e1c388d29e26ae2f0c55f8bb0216920ac776bb108f0c1a5b8dfeb0198"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-03T13:43:48.454339Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-03T13:43:48.260713Z",
          "state_after": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          },
          "state_before": {
            "digest": "f71282323390d670d7c977cd278838321fb7484fdcbacfdda0b6ae271b034816",
            "files": 34,
            "head": "e705b2d5835e6289bbb48a17a155d58b9befed9d"
          }
        }
      },
      "scope": {
        "dependencies": [
          "dashboard/index.html",
          "dashboard/package.json",
          "dashboard/src/styles/",
          "dashboard/tsconfig.json",
          "dashboard/vite.config.ts",
          "plugins/fullstack-agents/scripts/lib/dashboard.html",
          "plugins/fullstack-agents/scripts/lib/fleet.js"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/src/App.tsx",
          "dashboard/src/components/CardContextMenu.tsx",
          "dashboard/src/components/Header.tsx",
          "dashboard/src/components/OutDialog.tsx",
          "dashboard/src/components/Toasts.tsx",
          "dashboard/src/lib/api.ts",
          "dashboard/src/lib/cards.test.ts",
          "dashboard/src/lib/cards.ts",
          "dashboard/src/lib/clipboard.test.ts",
          "dashboard/src/lib/clipboard.ts",
          "dashboard/src/lib/format.test.ts",
          "dashboard/src/lib/format.ts",
          "dashboard/src/lib/markup.test.ts",
          "dashboard/src/lib/markup.ts",
          "dashboard/src/lib/types.ts",
          "dashboard/src/main.tsx",
          "dashboard/src/panel/Panel.tsx",
          "dashboard/src/store.ts",
          "dashboard/src/terminal/CardTerminal.tsx",
          "dashboard/src/terminal/HerdrOverlay.tsx",
          "dashboard/src/views/AgentsView.tsx",
          "dashboard/src/views/HerdrView.tsx",
          "dashboard/src/views/HistoryView.tsx",
          "none (new vitest files only)",
          "plugins/fullstack-agents/scripts/lib/dashboard-react/app.css",
          "plugins/fullstack-agents/scripts/lib/dashboard-react/app.js",
          "plugins/fullstack-agents/scripts/lib/dashboard-react/index.html"
        ],
        "rationale": "the build reads the manifest, configs and CSS; the port reads the old UI sources"
      },
      "spec_at": "2026-11-03T13:24:31.622900Z"
    },
    "U2": {
      "automated_waiver": null,
      "checks": {
        "BUILD": {
          "command": "cd dashboard && npx tsc -p . --noEmit 2>&1 | (! grep -E '^src/views/(AgentsView|agents/)') && npx vitest run src/views/agents",
          "cwd": ".",
          "definition_digest": "4fbac26138777a6213634df10be3b761acdb7e8b8c581db10d6af2fb922f6b58",
          "expect": {
            "none": "compile/lint success is silent"
          },
          "method": "command"
        },
        "C1": {
          "command": "npx tsc -p . --noEmit 2>&1 | (! grep -E '^src/views/(AgentsView|agents/)') && npx vitest run src/views/agents",
          "cwd": "dashboard",
          "definition_digest": "0a6b7d5dc533a4e915c8f60ffa7c0ac2fa3798a7d742f6d2cbf7efb602b90330",
          "expect": {
            "patterns": [
              "Tests +[0-9]+ passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "1cd47b664121beee44f3153e8e30e5f8d4fe6be1298726f827e3317a450c1b1d",
          "method": "inspection"
        },
        "R2": {
          "definition_digest": "fa1d1d41710eaa10a41571329587e2a06e3e497fc635a5105c40310717eaa7ad",
          "method": "review"
        },
        "R3": {
          "definition_digest": "b482a99d6073cf27a79777d4cb35a6d85dae471dcab89d37828c461b8cf24683",
          "method": "review"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "1",
          "text": "Own paths type-check and agents tests pass"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "2",
          "text": "Every agents* state in parity/states.mjs plus ctx-menu (right-clicking a card rendered by U2) is DOM-equal to the old UI"
        },
        {
          "checks": [
            "R2"
          ],
          "id": "3",
          "text": "Keyboard: Enter/Space open a focused card, w toggles wall (App), favourite buttons do not open the card"
        },
        {
          "checks": [
            "R3"
          ],
          "id": "4",
          "text": "No file outside ALLOWED_PATHS; store.ts/types.ts changes only reported"
        },
        {
          "checks": [
            "BUILD"
          ],
          "id": "BUILD",
          "text": "BUILD passes"
        }
      ],
      "kind": "code",
      "results": {},
      "scope": {
        "dependencies": [
          "dashboard/src/App.tsx",
          "dashboard/src/components/OutDialog.tsx",
          "dashboard/src/lib/",
          "dashboard/src/panel/Panel.tsx",
          "dashboard/src/store.ts",
          "plugins/fullstack-agents/scripts/lib/dashboard.html",
          "plugins/fullstack-agents/scripts/lib/fleet.js",
          "plugins/fullstack-agents/scripts/lib/orchestrators.js"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/src/views/AgentsView.tsx",
          "dashboard/src/views/agents/Activity.tsx",
          "dashboard/src/views/agents/FleetTiles.tsx",
          "dashboard/src/views/agents/FleetToolbar.tsx",
          "dashboard/src/views/agents/OrcCard.tsx",
          "dashboard/src/views/agents/Orchestrators.tsx",
          "dashboard/src/views/agents/Workers.tsx",
          "dashboard/src/views/agents/agents.test.ts",
          "dashboard/src/views/agents/agents.test.tsx",
          "dashboard/src/views/agents/tpm.ts",
          "none (new vitest file only)"
        ],
        "rationale": "the view reads U1's store and libs and calls U3's stubbed openAgent/openRunLog by their fixed signatures"
      },
      "spec_at": "2026-11-03T13:50:41.038700Z"
    },
    "U3": {
      "automated_waiver": null,
      "checks": {
        "BUILD": {
          "command": "cd dashboard && npx tsc -p . --noEmit 2>&1 | (! grep -E '^src/(panel/|components/OutDialog)') && npx vitest run src/panel",
          "cwd": ".",
          "definition_digest": "bbeaaf53368cfbaeb2fa846d1a0a4562ceae1872bcf0e2f2dcc0c5437c965846",
          "expect": {
            "none": "compile/lint success is silent"
          },
          "method": "command"
        },
        "C1": {
          "command": "npx tsc -p . --noEmit 2>&1 | (! grep -E '^src/(panel/|components/OutDialog)') && npx vitest run src/panel",
          "cwd": "dashboard",
          "definition_digest": "d69972c7fadca676c365015721c4f6dd3c3b3786c93ce42a8b3fdcfa844b7432",
          "expect": {
            "patterns": [
              "Tests +[0-9]+ passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "974f0db9c2d5c9562cf351e376929bc8cb06a7c6518066802c6621a9ca4c3b04",
          "method": "inspection"
        },
        "R2": {
          "definition_digest": "43f2ceac599e6a341a269cd5b3044ac17d4ee46a7313454245f939b3798a9c7d",
          "method": "review"
        },
        "R3": {
          "definition_digest": "e38643223f80b7a4a034172ace034ec902c9ddbc4ee235de4451ae4ce92cc4fb",
          "method": "review"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "1",
          "text": "Own paths type-check and panel tests pass"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "2",
          "text": "States panel-info, panel-git, panel-run-log, out-console, panel-close are DOM-equal to the old UI"
        },
        {
          "checks": [
            "R2"
          ],
          "id": "3",
          "text": "Must-haves (a)-(d) hold"
        },
        {
          "checks": [
            "R3"
          ],
          "id": "4",
          "text": "No file outside ALLOWED_PATHS; store.ts/types.ts changes only reported"
        },
        {
          "checks": [
            "BUILD"
          ],
          "id": "BUILD",
          "text": "BUILD passes"
        }
      ],
      "kind": "code",
      "results": {},
      "scope": {
        "dependencies": [
          "dashboard/src/App.tsx",
          "dashboard/src/lib/",
          "dashboard/src/store.ts",
          "dashboard/src/terminal/CardTerminal.tsx",
          "plugins/fullstack-agents/scripts/lib/dashboard.html",
          "tests/dashboard/test_information_ui.py"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/src/components/OutDialog.tsx",
          "dashboard/src/panel/GitTab.tsx",
          "dashboard/src/panel/InfoTab.tsx",
          "dashboard/src/panel/Panel.tsx",
          "dashboard/src/panel/PanelHead.tsx",
          "dashboard/src/panel/RunCards.tsx",
          "dashboard/src/panel/TaskList.tsx",
          "dashboard/src/panel/docs.ts",
          "dashboard/src/panel/panel.test.ts",
          "dashboard/src/panel/panel.test.tsx",
          "dashboard/src/panel/panelLib.ts",
          "none (new vitest file only)"
        ],
        "rationale": "the panel reads U1's store and libs and mounts U4's CardTerminal by its fixed {card} signature"
      },
      "spec_at": "2026-11-03T13:50:41.131934Z"
    },
    "U4": {
      "automated_waiver": null,
      "checks": {
        "BUILD": {
          "command": "cd dashboard && npx tsc -p . --noEmit 2>&1 | (! grep -E '^src/(terminal/|views/HerdrView)') && npx vitest run src/terminal",
          "cwd": ".",
          "definition_digest": "9550e218d5a604b2e5e1f70f855bf61106b53de07e6fc42d7838d64d76dbc8e0",
          "expect": {
            "none": "compile/lint success is silent"
          },
          "method": "command"
        },
        "C1": {
          "command": "npx tsc -p . --noEmit 2>&1 | (! grep -E '^src/(terminal/|views/HerdrView)') && npx vitest run src/terminal",
          "cwd": "dashboard",
          "definition_digest": "f56767e174c1dabaa7a9a5127e2f94a60cd15c76b32fdd0be95a20009a52877a",
          "expect": {
            "patterns": [
              "Tests +[0-9]+ passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "f68c62d5f9ee7fb72cadd2fc793cebcea842325977376fc214bd817ad7889bed",
          "method": "inspection"
        },
        "R2": {
          "definition_digest": "f9e48a1fe8d34ffd395c228dc2f939738f8d8df6daa16358fb1efc8b95cb648a",
          "method": "review"
        },
        "R3": {
          "definition_digest": "8261c1b8bfe2abaebda50aef061f66b4f9466a91724842891b7b7091dd22efcb",
          "method": "review"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "1",
          "text": "Own paths type-check and terminal tests pass"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "2",
          "text": "States panel-terminal, herdr-new-session, herdr are DOM-equal to the old UI"
        },
        {
          "checks": [
            "R2"
          ],
          "id": "3",
          "text": "Must-haves (a)-(e) hold"
        },
        {
          "checks": [
            "R3"
          ],
          "id": "4",
          "text": "No file outside ALLOWED_PATHS; store.ts/types.ts changes only reported"
        },
        {
          "checks": [
            "BUILD"
          ],
          "id": "BUILD",
          "text": "BUILD passes"
        }
      ],
      "kind": "code",
      "results": {},
      "scope": {
        "dependencies": [
          "dashboard/index.html",
          "dashboard/src/App.tsx",
          "dashboard/src/components/Header.tsx",
          "dashboard/src/lib/",
          "dashboard/src/store.ts",
          "plugins/fullstack-agents/scripts/lib/dashboard.html",
          "tests/dashboard/test_herdr_client_ui.py",
          "tests/dashboard/test_terminal_scroll.py"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/src/terminal/CardTerminal.tsx",
          "dashboard/src/terminal/HerdrOverlay.tsx",
          "dashboard/src/terminal/copy.test.ts",
          "dashboard/src/terminal/copy.ts",
          "dashboard/src/terminal/files.ts",
          "dashboard/src/terminal/herdrClient.ts",
          "dashboard/src/terminal/herdrMenus.tsx",
          "dashboard/src/terminal/liveTerminal.test.ts",
          "dashboard/src/terminal/liveTerminal.ts",
          "dashboard/src/terminal/osc52.test.ts",
          "dashboard/src/terminal/osc52.ts",
          "dashboard/src/terminal/snapshotTerminal.ts",
          "dashboard/src/views/HerdrView.tsx",
          "none (new vitest files only)"
        ],
        "rationale": "the terminals read U1's store and libs; the header button and xterm globals come from U1/U0"
      },
      "spec_at": "2026-11-03T13:50:41.198354Z"
    }
  },
  "runs": {},
  "schema": 1
}
```
<!-- fsa:evidence:end -->

## Ownership log
- 2026-11-03T13:09:18.581136Z adopted by 34f94a84-a134-4113-8eba-235795412266 from 978905e0-a5f6-4f3f-af8b-b26011a41634 (free)
- 2026-11-03T13:39:36.511004Z adopted by 74648219-b630-4dfc-9bf2-9f49d6dfc6fc from 34f94a84-a134-4113-8eba-235795412266 (free)
- 2026-11-03T13:46:51.071379Z adopted by 704b0464-bfd3-4f1b-a591-af0eec8e6151 from 74648219-b630-4dfc-9bf2-9f49d6dfc6fc (free)
