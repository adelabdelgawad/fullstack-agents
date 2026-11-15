# Addressed peer messages on team-board and a stall ladder for watched runs

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until | Parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | done | team-board send/inbox: speech act, hop cap, per-session cursor, with tests | 49/49 team-board.test.sh |  |  |  |  |
| M2 | done | peer-inbox hook delivers unread messages as information-only context | registered on PostToolUse * and UserPromptSubmit |  |  |  |  |
| M3 | done | Stall ladder and message docs (task-flow, skill-guide, team-coordination) | rule 4 rewritten, stall ladder, index refreshed |  |  |  |  |
| M4 | done | Release: version bump, Codex bundle regenerated, full checks, local commit | 3.85.0, bundle regenerated, all suites green, committed locally |  |  |  |  |
<!-- fsa:tasks:end -->

<!-- fsa:checkpoint:start -->
```json
{
  "approvals": [
    {
      "at": "2026-11-15",
      "clarity": "explicit",
      "kind": "task",
      "quote": "go ahead with that ideas",
      "scope": "implement both Munder Difflin ideas",
      "used": false
    }
  ],
  "blockers": [],
  "constraints": [
    "One-line comments only (global CLAUDE.md)",
    "Functions < 50 lines; keep main() from growing (helpers called in one line)",
    "Do not push: AGENTS.md binding names /home/adel/..., checkout is /home/ashadmin/...; ask the user",
    "Never change status/note output"
  ],
  "decisions": [
    {
      "id": "D1",
      "source": "lead + advisor",
      "text": "Messages live in board.json keys messages/inbox/msg_seq; TTL 48h, cap 200, text cap 500, MAX_HOPS 6; old binaries keep unknown keys"
    },
    {
      "id": "D2",
      "source": "advisor",
      "text": "send touches <board>.msg sentinel; hook peer-inbox starts Python only when sentinel is newer than per-session stamp in state_dir; stamp copied from sentinel before the run (touch -r to .new, mv after)"
    },
    {
      "id": "D3",
      "source": "lead + advisor",
      "text": "New cursor: direct messages always delivered; broadcasts only if younger than 60 min. --reply-to unknown/expired id exits 2; hop cap refuses at hops>6. Recipient resolved over claims/phases/steps/waits/inbox keys and message senders: id, unique 8+ char prefix, or unique claim/sender name; ambiguous refused; self refused; --to defaults to parent sender"
    },
    {
      "id": "D4",
      "source": "advisor",
      "text": "Hook skips agent_id (subagents share session_id) and FSA_IMPLEMENTER_RUN; FSA_PEER_INBOX=off disables; echoes hook_event_name; register on PostToolUse * and UserPromptSubmit; never blocks Stop"
    },
    {
      "id": "D5",
      "source": "advisor",
      "text": "team-coordination rule 4 rewritten: board send for addressed coordination between sessions; incidents still also need the user/other channel; no contradictory statements"
    },
    {
      "id": "D6",
      "source": "user-approved idea",
      "text": "Stall ladder in skill-guide Watching a run + task-flow SKILL.md line 90: 5 min no change -> inspect engine activity, record it; 5 more min none -> stop engine process, redispatch once; any observed change drops one level; second hang -> report"
    },
    {
      "id": "D7",
      "source": "lead",
      "text": "Tests for team-board.test.sh: send/inbox direct and broadcast; cursor advances; new-cursor rule (backdate a broadcast by editing board JSON); hop cap 6 ok, 7 refused; unknown reply-to exit 2; ambiguous name refused; self refused; --to defaults to parent sender"
    },
    {
      "id": "D8",
      "source": "advisor",
      "text": "More tests: old binary from git show ae040f6:plugins/fullstack-agents/scripts/team-board keeps messages after a claim; peer-inbox hook delivers once, skips agent_id, prints nothing without sentinel, echoes hook_event_name"
    },
    {
      "id": "D9",
      "source": "lead",
      "text": "Register peer-inbox in hooks.json on PostToolUse * (beside context-handoff, timeout 10) and UserPromptSubmit (timeout 10)"
    },
    {
      "id": "D10",
      "source": "lead",
      "text": "M4: bump 3.85.0 in .claude-plugin/marketplace.json and plugin.json; regenerate Codex bundle (build.py into empty tmp dir, sync into plugins/fullstack-agents-codex as f6f0fc8 did); rerun all suites; audit diff; commit locally with explicit paths"
    }
  ],
  "done": [
    {
      "evidence": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/1e3269eb-a58a-4524-b7f6-1ee3406646ee/scratchpad/base-*.log",
      "text": "Baseline green: 13 hook suites exit 0; tests/codex 232 OK; tests/dashboard 497 OK (run per folder: cd tests/X && python3 -m unittest discover -s .)"
    },
    {
      "evidence": "git diff plugins/fullstack-agents/scripts/team-board",
      "text": "team-board: send/inbox implemented (helpers one_line, known_sessions, resolve_recipient, send_message, unread, message_line, print_inbox, add_message_parsers, touch); parses, untested"
    },
    {
      "evidence": "plugins/fullstack-agents/hooks/peer-inbox",
      "text": "hooks/peer-inbox written and chmod +x; not yet registered in hooks.json; untested"
    }
  ],
  "evidence": [
    "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/17053500-d6f8-4546-8bb0-6e7035cbc860/scratchpad/handoff-board-messages.md"
  ],
  "goal": "Add addressed peer messages to team-board (send/inbox, speech act, hop cap, per-session cursor, hook delivery as information-only context) and a breaker-style stall ladder for watched runs; release locally, no push.",
  "identity": {
    "branch": "main",
    "checkout": "/home/ashadmin/workspace/fullstack-agents",
    "detached": false,
    "head": "ae040f62a83f32425648176f7642b2fe5913e750",
    "root": "/home/ashadmin/workspace/fullstack-agents",
    "schema": 1,
    "session_id": "1e3269eb-a58a-4524-b7f6-1ee3406646ee",
    "task_id": "board-messages",
    "written_at": "2026-11-15T13:16:33.992643Z"
  },
  "next": {
    "action": "Write the tests listed in decision D7 into hooks/team-board.test.sh and run it; then register peer-inbox in hooks.json; then M3 docs and M4 release as D7 says.",
    "owner": "lead"
  },
  "scope": {
    "in": [
      "plugins/fullstack-agents/scripts/team-board",
      "plugins/fullstack-agents/hooks/peer-inbox",
      "plugins/fullstack-agents/hooks/hooks.json",
      "plugins/fullstack-agents/hooks/team-board.test.sh",
      "plugins/fullstack-agents/skills/team-coordination/SKILL.md",
      "plugins/fullstack-agents/skills/task-flow/SKILL.md",
      "plugins/fullstack-agents/skills/task-flow/references/skill-guide.md",
      "plugins/fullstack-agents/hooks/session-start (line 109 text)",
      "version: .claude-plugin/marketplace.json, plugins/fullstack-agents/.claude-plugin/plugin.json (3.84.0 -> 3.85.0)",
      "plugins/fullstack-agents-codex (regenerated)"
    ],
    "out": [
      "status/note output format",
      "push to origin"
    ]
  },
  "status": "active",
  "verification": []
}
```
<!-- fsa:checkpoint:end -->

## Task log
<!-- fsa:log:start -->
- 2026-11-15T13:08:16Z - init
- 2026-11-15T13:17:53Z M2 status from="pending" to="in_progress" reason=""
- 2026-11-15T13:18:10Z M1 accept reason="" invalidated=""
- 2026-11-15T13:18:10Z M1 check_start check="C1" run="47b41e46ca2584a9e227de47ebbef7b3"
- 2026-11-15T13:18:20Z M1 check_finish check="C1" run="47b41e46ca2584a9e227de47ebbef7b3" result="pass" executor="tool" reason=""
- 2026-11-15T13:18:20Z M1 status from="in_progress" to="done" reason=""
- 2026-11-15T13:18:20Z M1 done_gate accepted="C1"
- 2026-11-15T13:18:40Z M2 accept reason="" invalidated=""
- 2026-11-15T13:18:40Z M2 check_start check="C1" run="7a64708b223af1ed5b3a636722269a6b"
- 2026-11-15T13:18:40Z M2 check_finish check="C1" run="7a64708b223af1ed5b3a636722269a6b" result="pass" executor="tool" reason=""
- 2026-11-15T13:18:40Z M2 status from="in_progress" to="done" reason=""
- 2026-11-15T13:18:40Z M2 done_gate accepted="C1"
- 2026-11-15T13:18:40Z M3 status from="pending" to="in_progress" reason=""
- 2026-11-15T13:19:39Z M3 accept reason="" invalidated=""
- 2026-11-15T13:19:40Z M3 check_start check="R1" run="aa652cb3c38c609464b4bf6f295e76a7"
- 2026-11-15T13:19:40Z M3 check_finish check="R1" run="aa652cb3c38c609464b4bf6f295e76a7" result="pass" executor="attested" reason=""
- 2026-11-15T13:19:40Z M3 status from="in_progress" to="done" reason=""
- 2026-11-15T13:19:40Z M3 done_gate accepted="R1"
- 2026-11-15T13:19:40Z M4 status from="pending" to="in_progress" reason=""
- 2026-11-15T13:23:46Z M4 accept reason="" invalidated=""
- 2026-11-15T13:23:47Z M4 check_start check="R1" run="3d926c16a416a36f9918f85587558602"
- 2026-11-15T13:23:47Z M4 check_finish check="R1" run="3d926c16a416a36f9918f85587558602" result="pass" executor="attested" reason=""
- 2026-11-15T13:23:49Z M4 check_start check="C1" run="0b853b7c4431558abd837f694ec5a757"
- 2026-11-15T13:26:58Z M4 check_finish check="C1" run="0b853b7c4431558abd837f694ec5a757" result="inconclusive" executor="tool" reason=""
- 2026-11-15T13:27:22Z M4 accept reason="summary grep: tail -n 3 missed the dashboard Ran line under test stdout" invalidated="C1"
- 2026-11-15T13:27:25Z M4 check_start check="C1" run="a7ace2c3e382b031374d2ecf1258a394"
- 2026-11-15T13:30:50Z M4 check_finish check="C1" run="a7ace2c3e382b031374d2ecf1258a394" result="pass" executor="tool" reason=""
- 2026-11-15T13:30:59Z M4 status from="in_progress" to="done" reason=""
- 2026-11-15T13:30:59Z M4 done_gate accepted="C1, R1"
- 2026-11-15T13:33:46Z M1 check_start check="C1" run="2c14d9d406e21a3579c8371ac9b289c4"
- 2026-11-15T13:33:53Z M1 check_finish check="C1" run="2c14d9d406e21a3579c8371ac9b289c4" result="pass" executor="tool" reason=""
- 2026-11-15T13:33:54Z M4 check_start check="C1" run="abbcb2bc02217034651ac317be3dfcf0"
- 2026-11-15T13:36:51Z M4 check_finish check="C1" run="abbcb2bc02217034651ac317be3dfcf0" result="pass" executor="tool" reason=""
- 2026-11-15T13:37:01Z M4 check_start check="R1" run="fc4402f2c311b858cdb7a58454f7dbab"
- 2026-11-15T13:37:01Z M4 check_finish check="R1" run="fc4402f2c311b858cdb7a58454f7dbab" result="pass" executor="attested" reason=""
- 2026-11-15T13:37:09Z M4 check_start check="C1" run="2e9ad95fa9b9c41bdaa720089b4afdb5"
- 2026-11-15T13:39:56Z M4 check_finish check="C1" run="2e9ad95fa9b9c41bdaa720089b4afdb5" result="pass" executor="tool" reason=""
- 2026-11-15T13:39:56Z M4 check_start check="R1" run="67eacd31a7f8a9a849f031d3d751127b"
- 2026-11-15T13:39:56Z M4 check_finish check="R1" run="67eacd31a7f8a9a849f031d3d751127b" result="pass" executor="attested" reason=""
<!-- fsa:log:end -->

<!-- fsa:evidence:start -->
```json
{
  "baselines": {},
  "deliverables": {
    "M1": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "bash plugins/fullstack-agents/hooks/team-board.test.sh",
          "cwd": ".",
          "definition_digest": "952c3ed4bc64ef4bbe82edd2a96f3fceba64f0addc691307644608d945da6688",
          "expect": {
            "patterns": [
              "[1-9][0-9]* passed, 0 failed"
            ],
            "reject": [
              "^FAIL"
            ]
          },
          "method": "command"
        }
      },
      "completed": {
        "at": "2026-11-15T13:18:20.869484Z",
        "with": {
          "C1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "AC1",
          "text": "send/inbox, cursor, hop cap, recipient rules and peer-inbox delivery behave as D3/D4/D7/D8"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "952c3ed4bc64ef4bbe82edd2a96f3fceba64f0addc691307644608d945da6688",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/527a0d739cd1d305/M1-C1-20261115T133346Z.log",
              "sha256": "e67d0a5b8e3ccd7dacf486bfb975b17988f69d1c49cbeef938bf892762d5cba0"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-15T13:33:53.915485Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-15T13:33:46.830213Z",
          "state_after": {
            "digest": "7da88af118421a928df5d25bd8d2fe79114c286e3fb62eaef66adff7a025b3a9",
            "files": 5,
            "head": "b0748c88d89368841a3b9f0b0d1851f9975ed280"
          },
          "state_before": {
            "digest": "7da88af118421a928df5d25bd8d2fe79114c286e3fb62eaef66adff7a025b3a9",
            "files": 5,
            "head": "b0748c88d89368841a3b9f0b0d1851f9975ed280"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/hooks/lib.sh",
          "plugins/fullstack-agents/scripts/fsa-task"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "plugins/fullstack-agents/scripts/team-board",
          "plugins/fullstack-agents/hooks/peer-inbox",
          "plugins/fullstack-agents/hooks/team-board.test.sh"
        ],
        "rationale": "send/inbox live in team-board; the hook reads lib.sh state_dir; the suite also drives fsa-task"
      },
      "spec_at": "2026-11-15T13:18:10.376828Z"
    },
    "M2": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "python3 /tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/fef83ac2-5c03-49b6-bb3d-f95bb9dc24ca/scratchpad/m2check.py",
          "cwd": ".",
          "definition_digest": "50149203531258050e0a16a21f1ddbb14ec1f16dffb0f6459683f2b7c9267c27",
          "expect": {
            "patterns": [
              "PostToolUse True",
              "UserPromptSubmit True"
            ],
            "reject": [
              "False"
            ]
          },
          "method": "command"
        }
      },
      "completed": {
        "at": "2026-11-15T13:18:40.774120Z",
        "with": {
          "C1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1"
          ],
          "id": "AC1",
          "text": "peer-inbox registered sync, timeout 10, on PostToolUse * and UserPromptSubmit"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "50149203531258050e0a16a21f1ddbb14ec1f16dffb0f6459683f2b7c9267c27",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/527a0d739cd1d305/M2-C1-20261115T131840Z.log",
              "sha256": "ea7c808be0c88fecb109144282e1e232854f2e9cf3bf9e809e17b314d063d903"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-15T13:18:40.716046Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-15T13:18:40.678596Z",
          "state_after": {
            "digest": "d72a0ae99dceddd790be0ebd04ec8f26683b3f26d1136552ac32d7d8c022ac83",
            "files": 2,
            "head": "ae040f62a83f32425648176f7642b2fe5913e750"
          },
          "state_before": {
            "digest": "d72a0ae99dceddd790be0ebd04ec8f26683b3f26d1136552ac32d7d8c022ac83",
            "files": 2,
            "head": "ae040f62a83f32425648176f7642b2fe5913e750"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/hooks/peer-inbox"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "plugins/fullstack-agents/hooks/hooks.json"
        ],
        "rationale": "registration only; hook behaviour is M1's suite"
      },
      "spec_at": "2026-11-15T13:18:40.619059Z"
    },
    "M3": {
      "automated_waiver": null,
      "checks": {
        "R1": {
          "definition_digest": "1ff5b779967aa06d9b1c146e6d413fea65eced1a1c441a7b58d22fe1b6077c41",
          "method": "review"
        }
      },
      "completed": {
        "at": "2026-11-15T13:19:40.253813Z",
        "with": {
          "R1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "R1"
          ],
          "id": "AC1",
          "text": "rule 4 and command block describe send/inbox without contradiction; stall ladder per D6 in guide and SKILL.md; guide index matches headings"
        }
      ],
      "kind": "docs",
      "results": {
        "R1": {
          "definition_digest": "1ff5b779967aa06d9b1c146e6d413fea65eced1a1c441a7b58d22fe1b6077c41",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/fef83ac2-5c03-49b6-bb3d-f95bb9dc24ca/scratchpad/m3.diff",
              "sha256": "dc42393cc0976ce8668ba119906104192044354ef77216fb09feb45c79634ba6"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-15T13:19:40.126482Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-15T13:19:40.045604Z",
          "state_after": {
            "digest": "f9646c68953b8e6f3c30a3692e0d03456e83d294c2033ebcac66fdf957b33e80",
            "files": 4,
            "head": "ae040f62a83f32425648176f7642b2fe5913e750"
          },
          "state_before": {
            "digest": "f9646c68953b8e6f3c30a3692e0d03456e83d294c2033ebcac66fdf957b33e80",
            "files": 4,
            "head": "ae040f62a83f32425648176f7642b2fe5913e750"
          }
        }
      },
      "scope": {
        "dependencies": [],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          "plugins/fullstack-agents/skills/team-coordination/SKILL.md",
          "plugins/fullstack-agents/skills/task-flow/SKILL.md",
          "plugins/fullstack-agents/skills/task-flow/references/skill-guide.md",
          "plugins/fullstack-agents/hooks/session-start"
        ],
        "rationale": "the four doc sites named in D5/D6 plus the session-start script line"
      },
      "spec_at": "2026-11-15T13:19:39.979905Z"
    },
    "M4": {
      "automated_waiver": null,
      "checks": {
        "C1": {
          "command": "bash -c 'for t in plugins/fullstack-agents/hooks/*.test.sh; do bash $t >/dev/null 2>&1 || echo FAILED $t; done; cd tests/codex && python3 -m unittest discover -s . 2>&1 | grep -E \"^(Ran|OK|FAILED)\"; cd ../dashboard && python3 -m unittest discover -s . 2>&1 | grep -E \"^(Ran|OK|FAILED)\"'",
          "cwd": ".",
          "definition_digest": "6bb3b081590d909c3545eb9b9bab7c6bd6c8e88463f5cb8ea04a009a024885f8",
          "expect": {
            "patterns": [
              "Ran 2[0-9][0-9] tests",
              "Ran 4[0-9][0-9] tests",
              "OK"
            ],
            "reject": [
              "FAILED"
            ]
          },
          "method": "command"
        },
        "R1": {
          "definition_digest": "b6c0458eab5aff17d1a62489fb0dd45e83f204c8de3f15d08b588143fee3d69d",
          "method": "review"
        }
      },
      "completed": {
        "at": "2026-11-15T13:30:59.240196Z",
        "with": {
          "C1": "pass",
          "R1": "pass"
        }
      },
      "criteria": [
        {
          "checks": [
            "C1",
            "R1"
          ],
          "id": "AC1",
          "text": "3.85.0 in both manifests; bundle regenerated from a clean export; all suites green"
        }
      ],
      "kind": "code",
      "results": {
        "C1": {
          "definition_digest": "6bb3b081590d909c3545eb9b9bab7c6bd6c8e88463f5cb8ea04a009a024885f8",
          "evidence": [
            {
              "path": "/home/ashadmin/.local/state/fullstack-agents/tasks/evidence/527a0d739cd1d305/M4-C1-20261115T133709Z.log",
              "sha256": "204a5fdb0a95804bf8a943c4659c3f762585bc02cf6e64a04e18501faf5ab0c9"
            }
          ],
          "executor": "tool",
          "exit": 0,
          "finished_at": "2026-11-15T13:39:56.532053Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-15T13:37:09.796847Z",
          "state_after": {
            "digest": "09fb4bca864169a96b2b2f6cccbce98f3941d1edd23c843b9d66f790cc8b59c1",
            "files": 515,
            "head": "b0748c88d89368841a3b9f0b0d1851f9975ed280"
          },
          "state_before": {
            "digest": "09fb4bca864169a96b2b2f6cccbce98f3941d1edd23c843b9d66f790cc8b59c1",
            "files": 515,
            "head": "b0748c88d89368841a3b9f0b0d1851f9975ed280"
          }
        },
        "R1": {
          "definition_digest": "b6c0458eab5aff17d1a62489fb0dd45e83f204c8de3f15d08b588143fee3d69d",
          "evidence": [
            {
              "path": "/tmp/claude-1001/-home-ashadmin-workspace-fullstack-agents/fef83ac2-5c03-49b6-bb3d-f95bb9dc24ca/scratchpad/m4-fix.diff",
              "sha256": "375a833d9f885bc791887c9429ff2968310c18a5b534c3cd19b8b98fabcddf8d"
            }
          ],
          "executor": "attested",
          "finished_at": "2026-11-15T13:39:56.819528Z",
          "reason": null,
          "result": "pass",
          "started_at": "2026-11-15T13:39:56.627837Z",
          "state_after": {
            "digest": "09fb4bca864169a96b2b2f6cccbce98f3941d1edd23c843b9d66f790cc8b59c1",
            "files": 515,
            "head": "b0748c88d89368841a3b9f0b0d1851f9975ed280"
          },
          "state_before": {
            "digest": "09fb4bca864169a96b2b2f6cccbce98f3941d1edd23c843b9d66f790cc8b59c1",
            "files": 515,
            "head": "b0748c88d89368841a3b9f0b0d1851f9975ed280"
          }
        }
      },
      "scope": {
        "dependencies": [
          "plugins/fullstack-agents/",
          "integrations/codex/",
          "tests/"
        ],
        "dependencies_none": null,
        "env": [],
        "inputs": [],
        "paths": [
          ".claude-plugin/marketplace.json",
          "plugins/fullstack-agents/.claude-plugin/plugin.json",
          "plugins/fullstack-agents-codex/"
        ],
        "rationale": "release files plus the regenerated bundle; the suites exercise the whole plugin"
      },
      "spec_at": "2026-11-15T13:27:22.756269Z"
    }
  },
  "runs": {},
  "schema": 1
}
```
<!-- fsa:evidence:end -->

## Ownership log
- 2026-11-15T13:16:59.760453Z adopted by fef83ac2-5c03-49b6-bb3d-f95bb9dc24ca from 1e3269eb-a58a-4524-b7f6-1ee3406646ee (free)
