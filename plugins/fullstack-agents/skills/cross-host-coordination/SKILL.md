---
name: cross-host-coordination
description: Work spanning two hosts that run one repository (an app host and a GPU or ASR host) — delegating to the remote Claude session through herdr, syncing commits both ways, ordered rollout.
---

# Cross-host coordination

Two hosts run the same repository: for example an application host (UI, production server, no GPU) and an ASR
host (GPU, transcription services). A Claude session runs on each. One of them, the **coordinator** (the session
the user works with), owns any task that needs changes on both. This skill is the protocol; the mechanics of
driving the other session live in [references/remote-session.md](references/remote-session.md). Same-host rules
(own worktree, deploy lock, migration claims) stay in `team-coordination`.

## Bindings

The project's `CLAUDE.md` names, per host: role, hostname, repository path, herdr locator (the pane's SSH
target or terminal title; pane ids change), shared remote, integration branch policy, how the running revision
is observed, and its deploy command. A missing value is discovered (remote-session reference) or asked for,
never invented. Nothing about a specific machine belongs in this skill.

## Ownership

1. **The coordinator owns the task to the end**, including delegated work: it plans, briefs, monitors, answers
   routine questions and plan approvals inside the authorized scope, reviews results, sends follow-ups, and
   writes the one final report. A sent prompt, an acknowledgement or an unverified "done" is not completion.
   Ask the user only for missing facts, scope changes, or authorization not yet granted.
2. **Each session owns its worktree and unfinished changes.** Only the owning session edits, commits, resolves
   conflicts in or deploys from its checkout. Nobody stashes, resets, cleans, force-pushes, switches a dirty
   worktree or touches another session's files. When the current worktree is dirty or owned by other work, the
   owner creates an isolated worktree for the task.
3. **Commits travel only through the shared remote.** An uncommitted change or an unpushed commit does not exist
   for the other host.
4. **Integration and deployment are separate actions.** Each follows the authorization already granted for the
   application task; approving a coordination or plugin task authorizes neither. The owning session deploys its
   host on the coordinator's instruction; the coordinator verifies end to end.

## Evidence

Local observation is authoritative. Label every fact in the ledger and the report:

| Label | Meaning |
|---|---|
| verified | a command the coordinator ran itself: its own checkout, or the shared remote (`git ls-remote`, fetch) |
| runtime-inspected | service output the coordinator read (health or version endpoint, image label, process) |
| reported | the other session's statement, with its source and observation time |
| stale | reported before a later change on that host |
| unknown | not observed; never filled in by inference |

Run `scripts/fsa-host-status` (plugin scripts) on each host; the remote session runs its own installed copy and
returns the JSON. It is read-only by default; `--fetch` explicitly updates remote-tracking metadata. Its commit
checks keep **ancestry** (the commit is in the target's history) apart from **patch equivalence** (an equal diff
exists, for example after a cherry-pick): equivalence prevents applying a change twice but proves neither identical
history nor identical runtime behaviour. Merge commits, root commits and unknown shas report `unknown`.
`--running <sha>` only compares a revision; proof that a service runs it is runtime evidence.

## State ladder

Track each change per host, each step with its own evidence; a later step is never inferred from an earlier one:

`implemented` → `committed` → `pushed` → `integrated (target branch)` → `tested` → `deployed` → `verified running`

## Workflow

1. **Preflight both hosts**: `fsa-host-status --role <role> --target <integration ref> --commits <shas>` locally;
   the same on the other host through its session, plus its running-revision evidence. Record host, worktree,
   branch, HEAD, dirty paths, upstream and ahead/behind, remote reachability, owning session, role and running
   revision with labels and times.
2. **Plan**: changes per host, shared contracts (API, payload, authentication, configuration, migration),
   dependencies, and the order of implementation, integration and rollout (below). Do not assume `main` is the
   source or target; name both for this task.
3. **Delegate** with a complete brief (reference): scope, acceptance criteria, constraints, the authorization
   granted, the integration ref, and what to report (commits, pushed branch, tests with log paths, blockers,
   remaining work).
4. **Monitor actively** until the remote work is accepted. Waiting on a session that can still progress is
   monitoring, never a ledger blocker that ends the turn; use a blocker only when the remote cannot progress
   (host unreachable, session gone, needs the user), and keep checking for recovery.
5. **Review**: fetch, read the pushed diff, rerun `fsa-host-status --commits`; send repairs as follow-ups.
6. **Synchronize** (next section), in the integrating session's own worktree.
7. **Validate**: each owner runs its tests; the coordinator reads the logs or excerpts and runs the cross-host
   check it can (contract test, end-to-end call). Production is never a preview; use an isolated preview where the
   project has one.
8. **Deploy** only under existing authorization, in rollout order, each host by its owner; verify each running
   revision with runtime evidence.
9. **Report** once (status block below), covering both hosts.

## Choosing the integration

Decide from ancestry, branch ownership, whether the branch is published or shared, and project policy; say why.

| Facts | Action |
|---|---|
| commit already in target history | nothing |
| patch-equivalent change already in target | do not apply again; verify behaviour, note the differing history |
| target is an ancestor of the source tip | fast-forward, if project policy allows |
| diverged, source branch published or shared | merge (or the project's policy); never rebase it automatically |
| diverged, source unpublished and owned by the integrating session | that owner may rebase it |
| one isolated non-merge commit, the rest of its branch unwanted | `cherry-pick -x`; later merges then show patch equivalence, not a duplicate |
| sha unknown locally | the owner pushes, then fetch |

**ASR → UCM** (an ASR fix UCM needs): the ASR session commits and pushes a branch; the coordinator fetches,
checks, and integrates into the target in its own worktree. **UCM → ASR** (a UCM change ASR needs): the change is
pushed first; the ASR session fetches and integrates it into its branch, in an isolated worktree if its current one
is dirty.

## Coupled changes and rollout order

For every contract crossing the hosts, write: producer, consumer, old and new shape, and which side tolerates
both. Then:

- **API or payload**: make the change additive; deploy the side that accepts both versions first (usually the
  provider of a new optional field, or the consumer of a new response shape); remove the old shape in a later release.
- **Authentication or configuration**: the setting exists on the host before code that reads it is deployed;
  secrets never appear in briefs, ledgers or reports.
- **Migration**: the side owning the database migrates; follow `team-coordination` (version claim, images carry
  every applied migration); backward-compatible schema first.
- **Partial rollout**: record per-host state. If one host deployed and the other failed or lags, confirm the
  deployed side still works with the old peer, or roll the other forward; report the mixed state until resolved.

Example: UCM starts sending `language` to ASR's job endpoint. ASR first accepts an optional `language` (default
unchanged) and deploys; UCM then sends it and deploys; the report shows both running revisions with runtime
evidence. Reversed, UCM's requests would be rejected by the old ASR during the gap.

## Recovery

| Situation | Action |
|---|---|
| remote host or session unavailable | keep UCM-side work going; mark the remote facts `unknown`; recover the pane (reference); if impossible, block the row and report |
| remote branch missing | the owner pushes it; until then it does not exist for this host |
| diverged history | choose by the table; never force-push to converge |
| merge or rebase conflict | the owner resolves it in its own worktree; the coordinator reviews the result |
| dirty worktree in the way | isolated worktree for the task; leave the dirty one untouched |
| partial rollout | see rollout order; the report states the mixed state |
| stale report | ask for a fresh `fsa-host-status`; do not act on the old one |

## Record and report

Use the task ledger (`fsa-task`): one row per host deliverable, its Note holding host, branch, commit and ladder
state; the checkpoint holds ownership, related commits, dependencies, blockers and next actions. No credentials.
The final report and every status update use one block:

| Host | Role | Branch | Commit | Dirty | Sync needed | Validation | Deployment (evidence) | Next |
|---|---|---|---|---|---|---|---|---|
