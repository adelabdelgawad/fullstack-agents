# Driving the remote session through herdr

The remote host's Codex session usually runs inside an SSH connection in a herdr pane on the coordinator's host.
herdr cannot see that Codex (its agent status reads `unknown`), so the coordinator reads the pane's screen and
types into it. Every command below is herdr's own CLI; load `herdr --skill` for anything not listed.

## Find the pane

Pane ids change between herdr sessions; locate the pane each time from the bindings' locator:

```bash
herdr pane list                              # every pane id
herdr pane process-info --pane <id>          # foreground argv, e.g. ["ssh", "user@10.0.0.6"]
herdr pane get <id>                          # terminal_title, e.g. "user@gpu-host: ~"
```

Exactly one pane must match the SSH target or title. None or several: ask the user; never type into a guess.

## Read its state

```bash
herdr pane read <id> --source visible                 # current screen
herdr pane read <id> --source recent --lines 400      # recent scrollback
```

When the remote Codex runs inside tmux over SSH, herdr sees only what tmux draws: the remote session's earlier
output is not in `--source recent` once it scrolls off. Ask for answers short enough to fit one screen, read each
answer as soon as the turn ends, and ask the session to repeat a part that scrolled away.

| On screen | State |
|---|---|
| `esc to interrupt` in the footer | working: do not type |
| a final `Waiting on:`, `Blocked:` or `Paused:` line above an empty prompt | turn ended; read why |
| `Would you like to proceed?` with numbered options | plan approval card |
| a numbered question or `Do you want to` card | question or permission card |
| a shell prompt (`user@host:...$`) | Codex is not running |

Before typing, confirm the state belongs to this task: never answer another task's card or interrupt active work.

## Type into it

```bash
herdr pane send-text <id> "<one line>"     # text only; keep a prompt on one line
herdr pane send-text <id> $'\r'            # then confirm, about one second later
herdr pane send-keys <id> down             # move a menu selection; esc cancels
```

`send-keys <id> enter` does not confirm Codex Code's menus, and a key sent while a card is still rendering is
dropped: wait a second, send the carriage return, then read the screen to confirm it took.

## Brief

One line, numbered parts, nothing secret:

> Coordinated task from the UCM session (I own follow-up): (1) Goal … (2) Scope: files/areas … (3) Acceptance: …
> (4) Constraints: own worktree only, isolated worktree if yours is dirty, no stash/reset/clean/force-push, do not
> touch unrelated work (5) Authorization: … (deploy: yes/no) (6) Integration ref: … (7) Report when done or
> blocked: `fsa-host-status --role <role> --commits <shas>` JSON, pushed branch, tests run with log paths,
> blockers, remaining work; end with a `Waiting on:` line.

## Monitor

Watch with the session's own background mechanisms (Monitor, or a background command), never a foreground sleep:

```bash
herdr pane wait-output <id> --regex 'Waiting on:|Blocked:|Paused:|Would you like to proceed|Do you want to' \
  --source visible --timeout 600000
```

On each wake: read the screen. A routine question or plan inside the brief's scope: answer it or approve it
(check the highlighted option with `pane read` first). A question outside scope or needing authorization not yet
granted: ask the user. A "done": inspect the evidence (pushed commits through `git ls-remote`/fetch, the JSON, log
excerpts) before accepting; send a follow-up for anything missing.

## Running revision

Ask the owning session for its runtime evidence: the command, its raw output and the time (for example the image
label of the running container, or a version endpoint on that host). Record it as `reported`, or as
`runtime-inspected` only when the coordinator read that output itself (on screen in the pane counts, a summary
does not). Without it the running revision is `unknown`.

## Restart and resume

A plugin update reaches a running session only after a restart. Before it, the session writes its checkpoint
(`fsa-task checkpoint` when a ledger is bound). Then: `/exit` (Codex prints `claude --resume <session-id>`),
relaunch with the same command line and configuration directory plus `--resume <session-id>`, and confirm the
conversation and any pending decision are back. Restart only an idle session, never during active work or an open
card.

Update the install the session actually loads. Without `--scope`, `claude plugin update <plugin>` auto-detects and
may update a leftover project-scope entry for the working directory while the enabled user-scope install stays old.
Before updating, have the session list its `installed_plugins.json` entries for the plugin and the `enabledPlugins`
setting that enables it, then run `claude plugin update <plugin> --scope <that scope>`. After the restart, confirm
the new version in the session-start plugin scripts path and the new skill in its skill list.

## Unavailable host or session

Pane gone, SSH dropped, or a shell prompt where Codex should be: report the remote facts as `unknown`, continue
local work, and ask the user to reconnect when the connection itself needs credentials. A relaunch of Codex in a
live SSH pane follows "Restart and resume".
