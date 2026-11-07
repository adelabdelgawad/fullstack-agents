# FSA workflow comparison runner (A baseline vs B Harness²-inspired loop)

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | done | Runner core: pinned workflow snapshot, isolated arms, measurement, independent evaluation, report, deterministic fixture | 36 deterministic tests OK, log scratchpad/verify/experiment-final.log; codex 220 OK, dashboard 422 OK; ruff clean; 5 mutations caught |  |  |  |  |
| D2 | done | Arm B bounded propose→probe→compose loop with edit allowlist and canned-reply policy | propose/probe/compose, allowlist, retry+fallback, KEEP_BASE label tested |  |  |  |  |
| D3 | done | Auth/config preflights and bounded real smoke test (≤ $6 API-equivalent total) | Needs dedicated OAuth token file from user (claude setup-token) |  |  |  |  |
| D4 | blocked | Usage docs (docs/EXPERIMENT_RUNNER.md) and request first real task | docs/EXPERIMENT_RUNNER.md written; first real task to be requested |  |  |  |  |
<!-- fsa:tasks:end -->

## Task log
<!-- fsa:log:start -->
- 2026-10-27T16:41:28Z - init
- 2026-10-27T16:59:24Z D1 status from="in_progress" to="verifying" reason=""
- 2026-10-27T16:59:24Z D2 status from="pending" to="verifying" reason=""
- 2026-10-27T17:12:31Z D4 status from="pending" to="verifying" reason=""
- 2026-10-27T17:12:36Z B1 block kind="user" rows="D3"
- 2026-10-27T17:20:49Z B2 block kind="user" rows="D1,D2,D4"
- 2026-10-28T03:48:42Z B2 resolve kind="user" reason="user did not answer the $6 reading; proceeding with the runner-only reading at caps preflight $0.25/call, A $1, B $3, reported"
- 2026-10-28T03:48:42Z D1 status from="blocked" to="verifying" reason="blocker B2 resolved"
- 2026-10-28T03:48:42Z D2 status from="blocked" to="verifying" reason="blocker B2 resolved"
- 2026-10-28T03:48:42Z D4 status from="blocked" to="verifying" reason="blocker B2 resolved"
- 2026-10-28T03:48:44Z B1 resolve kind="user" reason=""
- 2026-10-28T03:48:44Z D3 status from="blocked" to="blocked" reason="blocker B1 resolved"
- 2026-10-28T03:48:57Z B3 block kind="worker" rows="D1,D2,D3,D4"
- 2026-10-28T03:55:44Z D1 accept reason="" invalidated=""
- 2026-10-28T03:55:44Z D2 accept reason="" invalidated=""
- 2026-10-28T03:55:44Z D3 accept reason="" invalidated=""
- 2026-10-28T03:55:48Z D1 check_start check="C1" run="f499e0a9dcbb906e22b48cead9bffa4c"
- 2026-10-28T03:56:18Z D1 check_finish check="C1" run="f499e0a9dcbb906e22b48cead9bffa4c" result="pass" executor="tool" reason=""
- 2026-10-28T03:56:18Z D1 check_start check="C2" run="996a2bd03d66b6e28dbb3d81413b08cf"
- 2026-10-28T03:56:18Z D1 check_finish check="C2" run="996a2bd03d66b6e28dbb3d81413b08cf" result="pass" executor="tool" reason=""
- 2026-10-28T03:56:18Z D1 check_start check="R1" run="8a09f18e35d52476577cc94d6b4363bc"
- 2026-10-28T03:56:18Z D2 check_start check="C1" run="475cd4e62b89298da6a43ec03c63e93b"
- 2026-10-28T03:56:47Z D2 check_finish check="C1" run="475cd4e62b89298da6a43ec03c63e93b" result="pass" executor="tool" reason=""
- 2026-10-28T03:56:47Z D2 check_start check="C2" run="40f9ce82a7d80fd5cf1775eba6c472d5"
- 2026-10-28T03:56:47Z D2 check_finish check="C2" run="40f9ce82a7d80fd5cf1775eba6c472d5" result="pass" executor="tool" reason=""
- 2026-10-28T03:56:47Z D2 check_start check="R1" run="49a175f4c93bb3063012cf1657492c33"
- 2026-10-28T03:56:47Z D3 check_start check="C1" run="c7305d2f45fc48fe2c344782a945e27e"
- 2026-10-28T03:57:16Z D3 check_finish check="C1" run="c7305d2f45fc48fe2c344782a945e27e" result="pass" executor="tool" reason=""
- 2026-10-28T03:57:16Z D3 check_start check="C2" run="626d560b52faa79d2bc91e29ca6f6776"
- 2026-10-28T03:57:16Z D3 check_finish check="C2" run="626d560b52faa79d2bc91e29ca6f6776" result="pass" executor="tool" reason=""
- 2026-10-28T03:57:16Z D3 check_start check="R1" run="8b0be135164c3f8df63e9c682aa91deb"
- 2026-10-28T03:57:22Z D1 check_start check="R1" run="add48235b3b9f4b2e3d49609061f675a"
- 2026-10-28T03:57:22Z D1 check_finish check="R1" run="add48235b3b9f4b2e3d49609061f675a" result="pass" executor="attested" reason=""
- 2026-10-28T03:57:22Z D2 check_start check="R1" run="32c4eed220da2ac9129691320ec1519a"
- 2026-10-28T03:57:22Z D2 check_finish check="R1" run="32c4eed220da2ac9129691320ec1519a" result="pass" executor="attested" reason=""
- 2026-10-28T03:57:22Z D3 check_start check="R1" run="2a802a04070e470a87149f0ae685695a"
- 2026-10-28T03:57:23Z D3 check_finish check="R1" run="2a802a04070e470a87149f0ae685695a" result="pass" executor="attested" reason=""
- 2026-10-28T03:57:27Z B4 block kind="user" rows="D4"
- 2026-10-28T03:57:30Z B3 withdraw kind="worker" reason="smoke-1 finished exit 0 and was evaluated; worker blocker no longer applies"
- 2026-10-28T03:57:30Z D1 status from="blocked" to="verifying" reason="blocker B3 withdrawn"
- 2026-10-28T03:57:30Z D2 status from="blocked" to="verifying" reason="blocker B3 withdrawn"
- 2026-10-28T03:57:30Z D3 status from="blocked" to="blocked" reason="blocker B3 withdrawn"
- 2026-10-28T03:57:30Z D1 status from="verifying" to="done" reason=""
- 2026-10-28T03:57:30Z D1 done_gate accepted="C1, C2, R1"
- 2026-10-28T03:57:30Z D2 status from="verifying" to="done" reason=""
- 2026-10-28T03:57:30Z D2 done_gate accepted="C1, C2, R1"
- 2026-10-28T03:57:30Z D3 status from="blocked" to="done" reason=""
- 2026-10-28T03:57:30Z D3 done_gate accepted="C1, C2, R1"
- 2026-10-28T04:03:15Z D1 check_start check="C1" run="5e64f446010a6157dfc4b90c4d435dc9"
- 2026-10-28T04:03:43Z D1 check_finish check="C1" run="5e64f446010a6157dfc4b90c4d435dc9" result="pass" executor="tool" reason=""
- 2026-10-28T04:03:43Z D1 check_start check="C2" run="4df00e19e4137e0f484f3cea67a191ec"
- 2026-10-28T04:03:43Z D1 check_finish check="C2" run="4df00e19e4137e0f484f3cea67a191ec" result="pass" executor="tool" reason=""
- 2026-10-28T04:03:43Z D1 check_start check="R1" run="df579544a1db779c9b46ea34d2241688"
- 2026-10-28T04:03:43Z D1 check_finish check="R1" run="df579544a1db779c9b46ea34d2241688" result="pass" executor="attested" reason=""
- 2026-10-28T04:03:44Z D2 check_start check="C1" run="20b7ed6edf7cddea71320bf3f80386be"
- 2026-10-28T04:04:13Z D2 check_finish check="C1" run="20b7ed6edf7cddea71320bf3f80386be" result="pass" executor="tool" reason=""
- 2026-10-28T04:04:13Z D2 check_start check="C2" run="f0032ae0c042933e86cf66be6cc3a987"
- 2026-10-28T04:04:13Z D2 check_finish check="C2" run="f0032ae0c042933e86cf66be6cc3a987" result="pass" executor="tool" reason=""
- 2026-10-28T04:04:13Z D2 check_start check="R1" run="9e0696d2fb9c270c23a00af9780db224"
- 2026-10-28T04:04:13Z D2 check_finish check="R1" run="9e0696d2fb9c270c23a00af9780db224" result="pass" executor="attested" reason=""
- 2026-10-28T04:04:13Z D3 check_start check="C1" run="86697367dea84885b48f954ed29addbb"
- 2026-10-28T04:04:40Z D3 check_finish check="C1" run="86697367dea84885b48f954ed29addbb" result="pass" executor="tool" reason=""
- 2026-10-28T04:04:41Z D3 check_start check="C2" run="ca9e7091a4ec7b239c861679015f8e29"
- 2026-10-28T04:04:41Z D3 check_finish check="C2" run="ca9e7091a4ec7b239c861679015f8e29" result="pass" executor="tool" reason=""
- 2026-10-28T04:04:41Z D3 check_start check="R1" run="c51f616b54b2fbd93e8de2d04a7a38fb"
- 2026-10-28T04:04:42Z D3 check_finish check="R1" run="c51f616b54b2fbd93e8de2d04a7a38fb" result="pass" executor="attested" reason=""
<!-- fsa:log:end -->

<!-- fsa:evidence:start -->
```json
{
  "baselines": {},
  "deliverables": {
    "D1": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "python3 -m unittest discover -s tests/experiment",
          "cwd": ".",
          "definition_digest": "ca3191be5538146aac5f36473ba8652616d9433719553665b2db45a203bd2589",
          "expect": {
            "patterns": [
              "Ran [1-9][0-9]* tests",
              "\\nOK"
            ],
            "reject": [
              "FAILED"
            ]
          },
          "method": "command"
        },
        "C2": {
          "command": "uvx ruff check tests/experiment",
          "cwd": ".",
          "definition_digest": "a560c9ef3db2729f08260e4906da8bb7eaf20edb6f6a84e3aee9338fda8d6bb2",
          "expect": {
            "patterns": [
              "All checks passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
          "method": "inspection"
        }
      },
      "completed": {
        "at": "2026-10-28T03:57:30.764411Z",
        "with": {
          "C1": "pass",
          "C2": "pass",
          "R1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1",
            "C2"
          ],
          "id": "AC1",
          "text": "Deterministic suite passes (isolation, arm B loop, failures, replies, accounting, evaluation, preflight)"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "AC2",
          "text": "Bounded real smoke run smoke-1 evaluated with independent checks; report distinguishes acceptance, regressions, costs, replies"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "ca3191be5538146aac5f36473ba8652616d9433719553665b2db45a203bd2589",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/0a73937fa72d62cd/D1-C1-20261028T040315Z.log",
              "sha256": "2592032b61596b0e170ecfc8ce21680954154edb214678cb848b86909dcdc208"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-10-28T04:03:43.723298Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:03:15.801715Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        },
        "C2": {
          "definition_digest": "a560c9ef3db2729f08260e4906da8bb7eaf20edb6f6a84e3aee9338fda8d6bb2",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/0a73937fa72d62cd/D1-C2-20261028T040343Z.log",
              "sha256": "82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-10-28T04:03:43.855761Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:03:43.785567Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        },
        "R1": {
          "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/share/fullstack-agents/experiments/smoke-1/REPORT.md",
              "sha256": "984196a9543e1f18909aeeb0f0877a0bc215ef85bef3a4bd2328a845503c5c63"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-10-28T04:03:43.991120Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:03:43.922796Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/scripts/lib/usage.py",
          "plugins/fullstack-agents/scripts/lib/liveness.py"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "tests/experiment/"
        ],
        "rationale": "the runner and its fake CLI fixture; it imports usage and liveness from the plugin lib"
      },
      "spec_at": "2026-10-28T03:55:44.422007Z"
    },
    "D2": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "python3 -m unittest discover -s tests/experiment",
          "cwd": ".",
          "definition_digest": "ca3191be5538146aac5f36473ba8652616d9433719553665b2db45a203bd2589",
          "expect": {
            "patterns": [
              "Ran [1-9][0-9]* tests",
              "\\nOK"
            ],
            "reject": [
              "FAILED"
            ]
          },
          "method": "command"
        },
        "C2": {
          "command": "uvx ruff check tests/experiment",
          "cwd": ".",
          "definition_digest": "a560c9ef3db2729f08260e4906da8bb7eaf20edb6f6a84e3aee9338fda8d6bb2",
          "expect": {
            "patterns": [
              "All checks passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
          "method": "inspection"
        }
      },
      "completed": {
        "at": "2026-10-28T03:57:30.826843Z",
        "with": {
          "C1": "pass",
          "C2": "pass",
          "R1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1",
            "C2"
          ],
          "id": "AC1",
          "text": "Deterministic suite passes (isolation, arm B loop, failures, replies, accounting, evaluation, preflight)"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "AC2",
          "text": "Bounded real smoke run smoke-1 evaluated with independent checks; report distinguishes acceptance, regressions, costs, replies"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "ca3191be5538146aac5f36473ba8652616d9433719553665b2db45a203bd2589",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/0a73937fa72d62cd/D2-C1-20261028T040344Z.log",
              "sha256": "a706d4c3abc5e4261bc6723c6f3802f0f15431c23b0a25604bb8aa8c2473cca0"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-10-28T04:04:13.035036Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:03:44.108942Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        },
        "C2": {
          "definition_digest": "a560c9ef3db2729f08260e4906da8bb7eaf20edb6f6a84e3aee9338fda8d6bb2",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/0a73937fa72d62cd/D2-C2-20261028T040413Z.log",
              "sha256": "82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-10-28T04:04:13.139343Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:04:13.100656Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        },
        "R1": {
          "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/share/fullstack-agents/experiments/smoke-1/REPORT.md",
              "sha256": "984196a9543e1f18909aeeb0f0877a0bc215ef85bef3a4bd2328a845503c5c63"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-10-28T04:04:13.263155Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:04:13.201499Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/scripts/lib/usage.py",
          "plugins/fullstack-agents/scripts/lib/liveness.py"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "tests/experiment/"
        ],
        "rationale": "the runner and its fake CLI fixture; it imports usage and liveness from the plugin lib"
      },
      "spec_at": "2026-10-28T03:55:44.480746Z"
    },
    "D3": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "python3 -m unittest discover -s tests/experiment",
          "cwd": ".",
          "definition_digest": "ca3191be5538146aac5f36473ba8652616d9433719553665b2db45a203bd2589",
          "expect": {
            "patterns": [
              "Ran [1-9][0-9]* tests",
              "\\nOK"
            ],
            "reject": [
              "FAILED"
            ]
          },
          "method": "command"
        },
        "C2": {
          "command": "uvx ruff check tests/experiment",
          "cwd": ".",
          "definition_digest": "a560c9ef3db2729f08260e4906da8bb7eaf20edb6f6a84e3aee9338fda8d6bb2",
          "expect": {
            "patterns": [
              "All checks passed"
            ],
            "reject": []
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
          "method": "inspection"
        }
      },
      "completed": {
        "at": "2026-10-28T03:57:30.888974Z",
        "with": {
          "C1": "pass",
          "C2": "pass",
          "R1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1",
            "C2"
          ],
          "id": "AC1",
          "text": "Deterministic suite passes (isolation, arm B loop, failures, replies, accounting, evaluation, preflight)"
        },
        {
          "checks": [
            "R1"
          ],
          "id": "AC2",
          "text": "Bounded real smoke run smoke-1 evaluated with independent checks; report distinguishes acceptance, regressions, costs, replies"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "ca3191be5538146aac5f36473ba8652616d9433719553665b2db45a203bd2589",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/0a73937fa72d62cd/D3-C1-20261028T040413Z.log",
              "sha256": "fbf500835b6819fbc88ab4f9437143976c2f8828e37608cc197e59ae6bdfdae7"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-10-28T04:04:40.805919Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:04:13.383108Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        },
        "C2": {
          "definition_digest": "a560c9ef3db2729f08260e4906da8bb7eaf20edb6f6a84e3aee9338fda8d6bb2",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/0a73937fa72d62cd/D3-C2-20261028T040441Z.log",
              "sha256": "82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-10-28T04:04:41.864101Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:04:41.242542Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        },
        "R1": {
          "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/share/fullstack-agents/experiments/smoke-1/REPORT.md",
              "sha256": "984196a9543e1f18909aeeb0f0877a0bc215ef85bef3a4bd2328a845503c5c63"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-10-28T04:04:42.004552Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-10-28T04:04:41.941717Z",
          "state_after": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          },
          "state_before": {
            "digest": "754d6fd97373df2c93ba5072f53d9eb9858db986d158b75110c6d0616da7640b",
            "files": 25,
            "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/scripts/lib/usage.py",
          "plugins/fullstack-agents/scripts/lib/liveness.py"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "tests/experiment/"
        ],
        "rationale": "the runner and its fake CLI fixture; it imports usage and liveness from the plugin lib"
      },
      "spec_at": "2026-10-28T03:55:44.537039Z"
    }
  },
  "runs": {
    "49a175f4c93bb3063012cf1657492c33": {
      "check": "R1",
      "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
      "deliverable": "D2",
      "open": true,
      "started_at": "2026-10-28T03:56:47.597695Z",
      "state_before": {
        "digest": "7585da2fcd827721153191e7481ac31e90c3703e6ea021d410833719159b660d",
        "files": 25,
        "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
      }
    },
    "8a09f18e35d52476577cc94d6b4363bc": {
      "check": "R1",
      "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
      "deliverable": "D1",
      "open": true,
      "started_at": "2026-10-28T03:56:18.444293Z",
      "state_before": {
        "digest": "7585da2fcd827721153191e7481ac31e90c3703e6ea021d410833719159b660d",
        "files": 25,
        "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
      }
    },
    "8b0be135164c3f8df63e9c682aa91deb": {
      "check": "R1",
      "definition_digest": "d4c341e15f5ea14bea1aed469f443ccaa773f1a11584c76edbd3384700eceeae",
      "deliverable": "D3",
      "open": true,
      "started_at": "2026-10-28T03:57:16.894264Z",
      "state_before": {
        "digest": "7585da2fcd827721153191e7481ac31e90c3703e6ea021d410833719159b660d",
        "files": 25,
        "head": "3867c1a0ad131fe930d53ea2317200fe64161ebc"
      }
    }
  },
  "schema": 1
}
```
<!-- fsa:evidence:end -->

<!-- fsa:blockers:start -->
```json
{
  "blockers": {
    "B1": {
      "created_at": "2026-10-27T17:12:36.032188Z",
      "kind": "user",
      "next": "",
      "resolution": {
        "at": "2026-10-28T03:48:44.482839Z",
        "by": "tool",
        "evidence": "yes copy it",
        "reason": ""
      },
      "resumes": {
        "D3": "blocked"
      },
      "rows": [
        "D3"
      ],
      "status": "resolved",
      "text": "Create the dedicated token: claude setup-token, save it to ~/.config/fullstack-agents/experiment-oauth-token (mode 600)",
      "why": "preflight and the bounded real smoke test need isolated config dirs without copying refresh credentials"
    },
    "B2": {
      "created_at": "2026-10-27T17:20:49.218175Z",
      "kind": "user",
      "next": "",
      "resolution": {
        "at": "2026-10-28T03:48:42.030973Z",
        "by": "tool",
        "evidence": "yes copy it",
        "reason": "user did not answer the $6 reading; proceeding with the runner-only reading at caps preflight $0.25/call, A $1, B $3, reported"
      },
      "resumes": {
        "D1": "verifying",
        "D2": "verifying",
        "D4": "verifying"
      },
      "rows": [
        "D1",
        "D2",
        "D4"
      ],
      "status": "resolved",
      "text": "Confirm the $6 ceiling covers only runner-made model calls (preflight + smoke: Sonnet, A $1, B $3, preflight $0.25/call) and provide the dedicated token",
      "why": "D1/D2 close only after the bounded real smoke test; D4 requests the first real task after it passes"
    },
    "B3": {
      "created_at": "2026-10-28T03:48:57.005623Z",
      "kind": "worker",
      "next": "evaluate, report, read logs, accept rows",
      "resolution": {
        "at": "2026-10-28T03:57:30.702826Z",
        "by": "tool",
        "evidence": "",
        "reason": "smoke-1 finished exit 0 and was evaluated; worker blocker no longer applies"
      },
      "resumes": {
        "D1": "verifying",
        "D2": "verifying",
        "D3": "blocked",
        "D4": "verifying"
      },
      "rows": [
        "D1",
        "D2",
        "D3",
        "D4"
      ],
      "status": "withdrawn",
      "text": "Background smoke run smoke-1 (task bjutkjgst) executing arms A then B",
      "why": "end-to-end evidence for D1-D3 and the D4 request come from this run's logs"
    },
    "B4": {
      "created_at": "2026-10-28T03:57:27.631793Z",
      "kind": "user",
      "next": "",
      "resolution": null,
      "resumes": {
        "D4": "verifying"
      },
      "rows": [
        "D4"
      ],
      "status": "open",
      "text": "First real implementation task and its acceptance criteria for the comparison",
      "why": "the runner must not invent or select a task"
    }
  },
  "schema": 1
}
```
<!-- fsa:blockers:end -->
