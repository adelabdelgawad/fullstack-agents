# Session task tracking

For a multi-step implementation, maintain a dedicated Markdown task file in the bound repository (normally `docs/tasks/<task>.md`). Keep its scope, acceptance criteria and evidence there. Register it to the actual lead session and original session working directory. A phase journal reports workflow activity; it does not replace the task list.

Use the bundled helper to initialize, bind or update the file. Codex runs `python3 scripts/tasks.py`; Codex runs `scripts/fsa-task` from its plugin. The examples below show the Codex form:

```bash
python3 scripts/tasks.py init --root /absolute/project --file docs/tasks/example.md --title "Example implementation" --task 'T01|running|Inspect existing behavior|Trace the failing case' --task 'T02|pending|Implement and verify|'
python3 scripts/tasks.py set --root /absolute/project --file docs/tasks/example.md --id T01 --status done --note 'Reproduced; evidence saved in the task file'
python3 scripts/tasks.py bind --root /absolute/project --file docs/tasks/example.md
```

Codex phase reporting can bind the file with `scripts/phase.py --root /absolute/project --phase plan --tasks docs/tasks/example.md`. Once registered, every phase reads its current counts, and `complete` is refused while any task is pending, running or blocked, or the registered file is invalid. No task is automatically marked done by a phase change.

The helper defaults to `CODEX_THREAD_ID` or `CLAUDE_SESSION_ID`; pass `--session` when the lead ID is known and not exported. Do not invent a session ID. The registration lives outside the repository; the Markdown file stays versioned with the project. `FSA_TASKS_DIR` overrides the shared registry directory for tools and dashboard together.

The task table is bounded by `<!-- fsa:tasks:start -->` and `<!-- fsa:tasks:end -->` and has `ID | Status | Task | Note` columns. Preserve stable IDs. Use `pending`, `running`, `blocked`, `done`, `skipped` or `canceled`. Only `done` counts as completed. Keep evidence and the next action in the note; record an actual blocking dependency for `blocked`. Do not mark implementation done while its required validation or audit remains outstanding.

Update the file when work starts, finishes, blocks or changes scope, including after worker results are verified. The dashboard rereads the file and displays a dedicated Tasks section with counts, per-task status and a link to the Markdown. It shows an error for an invalid or missing registered file; it never turns unreadable work into completion. Do not duplicate a manually maintained task list in phase summaries.

After wiring a task file or changing dashboard support, verify the live session shows it and invite the user to check the dashboard UI. Do not claim a dashboard update based only on a file write.
