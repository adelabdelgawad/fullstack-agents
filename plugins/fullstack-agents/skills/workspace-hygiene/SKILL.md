---
name: workspace-hygiene
description: Disk cleanup of a development workspace — which worktrees, branches and build caches are safe to delete, and removing them without touching another session's work.
---

# Workspace hygiene

Start with the plugin's `scripts/fsa-hygiene [<root>] [--caches] [--no-size]`. It is read-only and
classifies every git worktree under the root:

| Verdict | Meaning | Removal |
|---|---|---|
| safe | clean, merged (in the default branch's history or every commit patch-equivalent there), no untracked files, no process inside | the project's worktree finish script, else `git worktree remove` |
| probably safe | as safe, but untracked files remain (briefs, notes, logs) | copy the untracked files aside first, then remove with `--force` |
| keep | main checkout, dirty, unmerged, locked, or a process runs in it | never, unless its owner says so |

`--caches` lists rebuildable directories (`target`, `.next`, `node_modules`, ...) with sizes.

## Procedure

1. Report first, delete second: show the groups with sizes and ask which groups to remove. Only
   the user's answer authorizes deletion; a group approved once covers that group only.
2. Before removing, re-run the report: a worktree that changed state since the report moves to keep.
3. Claims: when other sessions share the repository, read the team board (`team-coordination`); a
   claimed path is keep.
4. Branches: delete a branch only after its worktree is gone and it is merged; `git branch -d`
   (never `-D`) unless the user approves that branch by name. A branch merged only by patch
   equivalence fails `-d`; when a guard hook blocks `-D`, list it with the command for the user to run
   on that host. Project guard hooks win.
5. Caches: never clean a shared cache while a peer builds (`team-coordination`, shared build cache).
6. Production data, media stores and quarantines are not workspace hygiene: report them, never delete.
7. Report what was removed, the space freed (`df -h` before and after), and where backups went.
