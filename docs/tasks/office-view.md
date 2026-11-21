# Office view: sessions as pixel employees in the dashboard

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| O1 | done | Office module (model, renderer, view, css, tests) | Codex unit A audited; lead fixed worker pose leak + test; office vitest 11/11 green; full suite after unit B | codex | Codex unit A building office module |  |  |
| O2 | done | Routing wiring (/next/office, tab, server route) + build + audit | lead direct edit |  |  |  |  |
<!-- fsa:tasks:end -->

## Task log
<!-- fsa:log:start -->
- 2026-11-21T15:43:57Z - init
- 2026-11-21T15:45:32Z B1 block kind="worker" rows="O1,O2"
- 2026-11-21T15:51:04Z B2 block kind="worker" rows="O2"
- 2026-11-21T15:51:07Z B1 withdraw kind="worker" reason="unit A landed and was audited"
- 2026-11-21T15:51:07Z O1 status from="blocked" to="in_progress" reason="blocker B1 withdrawn"
- 2026-11-21T15:51:07Z O1 status from="in_progress" to="verifying" reason=""
- 2026-11-21T15:51:14Z B3 block kind="worker" rows="O1"
- 2026-11-21T15:55:37Z B2 withdraw kind="worker" reason="unit B landed and audited"
- 2026-11-21T15:55:37Z O2 status from="blocked" to="pending" reason="blocker B2 withdrawn"
- 2026-11-21T15:55:37Z B3 withdraw kind="worker" reason="integrated checks ran"
- 2026-11-21T15:55:37Z O1 status from="blocked" to="verifying" reason="blocker B3 withdrawn"
- 2026-11-21T15:56:03Z O1 accept reason="" invalidated=""
- 2026-11-21T15:56:03Z O1 check_start check="C1" run="93518fa85b52edfb0f2b42daccb931ab"
- 2026-11-21T15:56:12Z O1 check_finish check="C1" run="93518fa85b52edfb0f2b42daccb931ab" result="pass" executor="tool" reason=""
- 2026-11-21T15:56:12Z O1 check_start check="C2" run="9a3560a01c50723b5d602485ba8db009"
- 2026-11-21T15:56:13Z O1 check_finish check="C2" run="9a3560a01c50723b5d602485ba8db009" result="inconclusive" executor="tool" reason=""
- 2026-11-21T15:56:14Z O1 check_start check="I1" run="338eb900e75aa039d2894fd8c581a05b"
- 2026-11-21T15:56:14Z O1 check_finish check="I1" run="338eb900e75aa039d2894fd8c581a05b" result="pass" executor="attested" reason=""
- 2026-11-21T15:56:14Z O2 accept reason="" invalidated=""
- 2026-11-21T15:56:14Z O2 check_start check="C1" run="d81e5f6050dfee48fad188e70916e772"
- 2026-11-21T15:56:22Z O2 check_finish check="C1" run="d81e5f6050dfee48fad188e70916e772" result="pass" executor="tool" reason=""
- 2026-11-21T15:56:23Z O2 check_start check="C2" run="c2786f7bdcd3332239b3b322239b90c2"
- 2026-11-21T15:56:23Z O2 check_finish check="C2" run="c2786f7bdcd3332239b3b322239b90c2" result="inconclusive" executor="tool" reason=""
- 2026-11-21T15:56:24Z O2 check_start check="I1" run="953ca27a081e3c5d532e7a9c3060d31e"
- 2026-11-21T15:56:24Z O2 check_finish check="I1" run="953ca27a081e3c5d532e7a9c3060d31e" result="pass" executor="attested" reason=""
- 2026-11-21T15:56:35Z O1 accept reason="C2 captures stderr" invalidated="C2"
- 2026-11-21T15:56:35Z O1 check_start check="C2" run="0bcb59c9812d4a25e9bd1720983e189d"
- 2026-11-21T15:56:36Z O1 check_finish check="C2" run="0bcb59c9812d4a25e9bd1720983e189d" result="pass" executor="tool" reason=""
- 2026-11-21T15:56:36Z O1 status from="verifying" to="done" reason=""
- 2026-11-21T15:56:36Z O1 done_gate accepted="C1, C2, I1"
- 2026-11-21T15:56:36Z O2 accept reason="C2 captures stderr" invalidated="C2"
- 2026-11-21T15:56:36Z O2 check_start check="C2" run="ddc92bbc68a97af64e824831ceb3e69d"
- 2026-11-21T15:56:37Z O2 check_finish check="C2" run="ddc92bbc68a97af64e824831ceb3e69d" result="pass" executor="tool" reason=""
- 2026-11-21T15:56:37Z O2 status from="pending" to="done" reason=""
- 2026-11-21T15:56:37Z O2 done_gate accepted="C1, C2, I1"
<!-- fsa:log:end -->

<!-- fsa:evidence:start -->
```json
{
  "baselines": {},
  "deliverables": {
    "O1": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "npx tsc -b && npx vitest run",
          "cwd": "dashboard",
          "definition_digest": "b1baab5d9c980a92d17cc327e7d582e37e047f1c3f9f38275bd7d978608da5df",
          "expect": {
            "patterns": [
              "Tests +[1-9][0-9]* passed"
            ],
            "reject": [
              "failed"
            ]
          },
          "method": "command"
        },
        "C2": {
          "command": "python3 -m unittest -k react_ui_served test_herdr_web 2>&1",
          "cwd": "tests/dashboard",
          "definition_digest": "30a8118b7038faf9661a8044f6acc50d68a655523eeff842039086d7743eec6f",
          "expect": {
            "patterns": [
              "Ran [1-9][0-9]* tests? in",
              "(?m)^OK"
            ],
            "reject": []
          },
          "method": "command"
        },
        "I1": {
          "definition_digest": "cdfe8024403b7af8b2dd1975cbfee7d921d815b3e88e9bc93cb0992604e11306",
          "method": "inspection"
        }
      },
      "completed": {
        "at": "2026-11-21T15:56:36.680089Z",
        "with": {
          "C1": "pass",
          "C2": "pass",
          "I1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1",
            "C2",
            "I1"
          ],
          "id": "AC1",
          "text": "Office view types, tests and renders with live sessions"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "b1baab5d9c980a92d17cc327e7d582e37e047f1c3f9f38275bd7d978608da5df",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/025f16c3f9263609/O1-C1-20261121T155603Z.log",
              "sha256": "ada4627d3172d64605c7bd663c810bb9285475a0bfeaf7b0e898100df0d1ac33"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-21T15:56:12.740183Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-21T15:56:03.379859Z",
          "state_after": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          },
          "state_before": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          }
        },
        "C2": {
          "definition_digest": "30a8118b7038faf9661a8044f6acc50d68a655523eeff842039086d7743eec6f",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/025f16c3f9263609/O1-C2-20261121T155635Z.log",
              "sha256": "ecc699e907821ae66b1fc5008186288159bbd383e529fa4c8126aaf5cd1fd306"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-21T15:56:36.547559Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-21T15:56:35.873544Z",
          "state_after": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          },
          "state_before": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          }
        },
        "I1": {
          "definition_digest": "cdfe8024403b7af8b2dd1975cbfee7d921d815b3e88e9bc93cb0992604e11306",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-keep-connect/966491a0-627f-44d2-96ee-3d75fd911fea/scratchpad/office-click.png",
              "sha256": "e326772e3cf8c7fb7d61faf1851713b9c30a0796590b8e05a8961c95a425333a"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-21T15:56:14.217718Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-21T15:56:14.074445Z",
          "state_after": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          },
          "state_before": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          }
        }
      },
      "scope": {
        "dependencies": [
          "dashboard/src/lib/",
          "dashboard/package.json",
          "dashboard/package-lock.json"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/src/views/office/",
          "dashboard/src/views/OfficeView.tsx",
          "dashboard/src/styles/office.css",
          "dashboard/src/store.ts",
          "dashboard/src/App.tsx",
          "dashboard/src/components/Layout.tsx",
          "dashboard/src/components/layout.test.tsx"
        ],
        "rationale": "office view and its routing; vitest and tsc cover the whole dashboard package including the lib helpers it calls"
      },
      "spec_at": "2026-11-21T15:56:35.793818Z"
    },
    "O2": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "npx tsc -b && npx vitest run",
          "cwd": "dashboard",
          "definition_digest": "b1baab5d9c980a92d17cc327e7d582e37e047f1c3f9f38275bd7d978608da5df",
          "expect": {
            "patterns": [
              "Tests +[1-9][0-9]* passed"
            ],
            "reject": [
              "failed"
            ]
          },
          "method": "command"
        },
        "C2": {
          "command": "python3 -m unittest -k react_ui_served test_herdr_web 2>&1",
          "cwd": "tests/dashboard",
          "definition_digest": "30a8118b7038faf9661a8044f6acc50d68a655523eeff842039086d7743eec6f",
          "expect": {
            "patterns": [
              "Ran [1-9][0-9]* tests? in",
              "(?m)^OK"
            ],
            "reject": []
          },
          "method": "command"
        },
        "I1": {
          "definition_digest": "cdfe8024403b7af8b2dd1975cbfee7d921d815b3e88e9bc93cb0992604e11306",
          "method": "inspection"
        }
      },
      "completed": {
        "at": "2026-11-21T15:56:37.586177Z",
        "with": {
          "C1": "pass",
          "C2": "pass",
          "I1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1",
            "C2",
            "I1"
          ],
          "id": "AC1",
          "text": "Office view types, tests and renders with live sessions"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "b1baab5d9c980a92d17cc327e7d582e37e047f1c3f9f38275bd7d978608da5df",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/025f16c3f9263609/O2-C1-20261121T155614Z.log",
              "sha256": "9f9d2f6f168bc44183d873c0171f5a9b696ce29f3d333005a6410f4d95309854"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-21T15:56:22.978587Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-21T15:56:14.377278Z",
          "state_after": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          },
          "state_before": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          }
        },
        "C2": {
          "definition_digest": "30a8118b7038faf9661a8044f6acc50d68a655523eeff842039086d7743eec6f",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/025f16c3f9263609/O2-C2-20261121T155636Z.log",
              "sha256": "ecc699e907821ae66b1fc5008186288159bbd383e529fa4c8126aaf5cd1fd306"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-21T15:56:37.423251Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-21T15:56:36.801513Z",
          "state_after": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          },
          "state_before": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          }
        },
        "I1": {
          "definition_digest": "cdfe8024403b7af8b2dd1975cbfee7d921d815b3e88e9bc93cb0992604e11306",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-keep-connect/966491a0-627f-44d2-96ee-3d75fd911fea/scratchpad/office-click.png",
              "sha256": "e326772e3cf8c7fb7d61faf1851713b9c30a0796590b8e05a8961c95a425333a"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-21T15:56:24.263671Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-21T15:56:24.072040Z",
          "state_after": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          },
          "state_before": {
            "digest": "19f93c736366e0df7a0ceb9deac1ae5c8ca25f4f0f9c1d6f85eb5ec12f2799b9",
            "files": 21,
            "head": "c00555dd6f940410c5a15687b691fe80ea587745"
          }
        }
      },
      "scope": {
        "dependencies": [
          "dashboard/src/lib/",
          "dashboard/package.json",
          "dashboard/package-lock.json"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "dashboard/src/views/office/",
          "dashboard/src/views/OfficeView.tsx",
          "dashboard/src/styles/office.css",
          "dashboard/src/store.ts",
          "dashboard/src/App.tsx",
          "dashboard/src/components/Layout.tsx",
          "dashboard/src/components/layout.test.tsx"
        ],
        "rationale": "office view and its routing; vitest and tsc cover the whole dashboard package including the lib helpers it calls"
      },
      "spec_at": "2026-11-21T15:56:36.740033Z"
    }
  },
  "runs": {},
  "schema": 1
}
```
<!-- fsa:evidence:end -->

<!-- fsa:blockers:start -->
```json
{
  "blockers": {
    "B1": {
      "created_at": "2026-11-21T15:45:32.811495Z",
      "kind": "worker",
      "next": "audit unit A, dispatch unit B brief",
      "resolution": {
        "at": "2026-11-21T15:51:07.668992Z",
        "by": "tool",
        "evidence": "",
        "reason": "unit A landed and was audited"
      },
      "resumes": {
        "O1": "in_progress",
        "O2": "pending"
      },
      "rows": [
        "O1",
        "O2"
      ],
      "status": "withdrawn",
      "text": "Codex unit A (office module) is running; O2 routing dispatches when it lands",
      "why": ""
    },
    "B2": {
      "created_at": "2026-11-21T15:51:04.007429Z",
      "kind": "worker",
      "next": "audit unit B, build bundle, render page",
      "resolution": {
        "at": "2026-11-21T15:55:37.766266Z",
        "by": "tool",
        "evidence": "",
        "reason": "unit B landed and audited"
      },
      "resumes": {
        "O2": "pending"
      },
      "rows": [
        "O2"
      ],
      "status": "withdrawn",
      "text": "Codex unit B (routing: store/App/Layout/layout.test) is running",
      "why": ""
    },
    "B3": {
      "created_at": "2026-11-21T15:51:14.954640Z",
      "kind": "worker",
      "next": "run tsc+vitest on integrated state",
      "resolution": {
        "at": "2026-11-21T15:55:37.830040Z",
        "by": "tool",
        "evidence": "",
        "reason": "integrated checks ran"
      },
      "resumes": {
        "O1": "verifying"
      },
      "rows": [
        "O1"
      ],
      "status": "withdrawn",
      "text": "Full suite and tsc for O1 run after Codex unit B lands (shared App/store build)",
      "why": ""
    }
  },
  "schema": 1
}
```
<!-- fsa:blockers:end -->

## Plan

Outcome: a fourth dashboard view, `/next/office`, draws every live session as a pixel-art employee at a desk.
Visuals cost 0 tokens: they come only from the existing 4 s `/api/state` poll in the store, drawn with Canvas 2D,
procedural pixel art, no external assets and no new requests. Clicking an employee opens a side card; its message box
posts `{pane, kind: "prompt", text}` to the existing `/api/herdr/send` (`herdr agent prompt`), so a message costs what a
typed prompt in that session costs. Sessions without a herdr pane (`state.session_panes`) are view-only.

| Unit | Owner | Files |
|---|---|---|
| A office module | implementer | `dashboard/src/views/office/{model.ts,model.test.ts,draw.ts}`, `dashboard/src/views/OfficeView.tsx`, `dashboard/src/styles/office.css` |
| B routing | lead | `dashboard/src/store.ts`, `App.tsx`, `components/Layout.tsx`, `components/layout.test.tsx`, `plugins/fullstack-agents/scripts/fsa-dashboard` (route list), `tests/dashboard/test_herdr_web.py`, built `scripts/lib/dashboard-react/*` |

Pose mapping (model): waits on the user -> `waiting`; quiet/stale -> `asleep`; running tool that reads/searches -> `reading`;
other running tool -> `typing`; else `idle`. One desk cluster per card (team); running implementer runs and card
subagents sit as helpers beside the lead.

Acceptance: vitest green (new model tests + existing suite); `tsc -b` and `vite build` green; python dashboard route test
green; page rendered and looked at in a browser with live state; message send verified against one test herdr pane.
Deploy class: plugin release (dashboard bundle), no service migration. Risk: none on lifecycle; `/api/herdr/send` already
validates pane and text.
