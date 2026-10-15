# Codex hooks across plugin upgrades

Repository: `/home/adel/workspace/fullstack-agents`, branch `main`.
Related UCM session: `01a13da9-31cd-7173-ac5d-dd655e7d804d`; application remains on dev.

<!-- fsa:tasks:start -->
| ID | Status | Task | Note |
| --- | --- | --- | --- |
| H01 | done | Reproduce stale absolute hook path after cache eviction | Session retains old PLUGIN_ROOT while plugin upgrade removes that directory. |
| H02 | done | Ship resilient hook dispatch and regression tests | Embedded standard-library bootstrap resolves current or newest valid sibling version; no deleted-cache script dependency. |
| H03 | in_progress | Audit, release and reload verified bundle | Check captured command after simulated cache eviction and installed hook invocation. |
<!-- fsa:tasks:end -->

Existing sessions with legacy direct-file commands receive compatibility links during this repair. Future generated manifests embed their resolver so they work after old version directories disappear. No application service rebuild or reload is needed.

52integrationtests PASS; independent audit qz0kcxrg PASS after isolatedPythonstartup/siblingimports repair. Parallel dashboard accuracy work: [tracking](dashboard-task-accuracy.md).
