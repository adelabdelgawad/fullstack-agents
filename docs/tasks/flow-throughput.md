# Agent flow throughput correction

<!-- fsa:tasks:start -->
| ID | Status | Task | Note | Owner | Activity | Active until |
| --- | --- | --- | --- | --- | --- | --- |
| F01 | done | Identify repeated workflow delays | Verified tiny audit units, scope-extension waits and idle-worker messaging |  |  |  |
| F02 | done | Update shared and Codex workflow | Deliverable-sized work, autonomous bounded reads and actual dispatch |  |  |  |
| F03 | done | Validate and independently audit | Generated bundle, integration tests and bounded Opus review | lead | 45 tests, skill validators, 231 generated files and 12 anchors verified; audit completed, unsupported findings rejected with source evidence |  |
| F04 | done | Commit publish and refresh plugin | Dev branch only, refresh Claude and Codex bundles | lead | 3.58.5 pushed; Claude reloaded; fresh Codex loaded 38 skills; installed sources match |  |
<!-- fsa:tasks:end -->

Validation: 45 Codex integration tests and both skill validators pass. All 231 generated files match the canonical builder; all 12 guide index targets match actual headings. Initial independent audit passed (wcppmqg0). Later audits found generated role wording and stale guide indexes; both were repaired. Final m31r5ez5 interpretation was rejected: the preamble explicitly says "in the Codex-led flow", preserves actual tool permissions, and never permits skipping diff review or required checks. The term "historical" refers to dispatcher rules inherited by that runtime; the Claude entrypoint still binds its current dispatcher. No final blanket PASS is claimed. Earlier hash/index allegations were disproved by current file hashes and actual heading locations.

Release 3.58.5 is pushed on omnichannel-dev. Claude user installation upgraded from 3.58.4 and reload succeeded (1 plugin, 40 skills, 9 agents, 9 hooks). A fresh Codex runtime forced skills reload and returned 38 skills from 3.58.5; both installed task-flow sources match released bytes.
