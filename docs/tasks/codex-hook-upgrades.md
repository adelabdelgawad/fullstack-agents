# Codex hooks across plugin upgrades

Repository: `/home/adel/workspace/fullstack-agents`, branch `main`.
Related UCM session: `01a13da9-31cd-7173-ac5d-dd655e7d804d`; application remains on dev.

<!-- fsa:tasks:start -->
| ID | Status | Task | Note |
| --- | --- | --- | --- |
| H01 | done | Reproduce stale absolute hook path after cache eviction | Session retains old PLUGIN_ROOT while plugin upgrade removes that directory. |
| H02 | done | Ship resilient hook dispatch and regression tests | Embedded standard-library bootstrap resolves current or newest valid sibling version; no deleted-cache script dependency. |
| H03 | done | Audit, release and reload verified bundle | Check captured command after simulated cache eviction and installed hook invocation. |
<!-- fsa:tasks:end -->

Existing sessions with legacy direct-file commands receive compatibility links during this repair. Future generated manifests embed their resolver so they work after old version directories disappear. No application service rebuild or reload is needed.

52integrationtests PASS; independent audit qz0kcxrg PASS after isolatedPythonstartup/siblingimports repair. Parallel dashboard accuracy work: [tracking](dashboard-task-accuracy.md).

Released3.59.1, committed/pushed `2a54157` directly onmain. FreshCodexforceReload verified38skills at3.59.1; installedgeneratedhook executed successfully with deliberatelymissingcapturedroot. Claudeuserplugin updated3.59.0→3.59.1 (existingClaude processes apply viareload/restart). Currentlegacy3.58.5/3.58.6/3.59.0scriptlinks pointto3.59.1. Theembedded resolver, ratherthanthoselinks, is thefuture-upgradefix.
