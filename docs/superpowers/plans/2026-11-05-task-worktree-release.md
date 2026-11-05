# Task worktree evidence and dashboard release

- Preserve completed dark RetroUI dashboard, compact cards, overflow fix, and separate page URLs.
- Add explicit `scope.worktree` for task evidence; validate it is a registered worktree of the same Git repository.
- Run checks, fingerprint files, and validate evidence against that checkout while retaining ledger ownership and location.
- Reject unrelated repositories, escaped scope paths, removed worktrees, and stale results.
- Test worker blocker resolution and document closing worker blockers separately from deliverable completion.
- Verify task evidence, blocker, tracking, and Codex packaging suites; perform local diff review. External Claude audit was rejected by automatic approval review and was not run.
- Release a new plugin version on main, preserving unrelated working changes; rebuild Codex package from the release scope.
- Refresh the installed package and dashboard; hook changes require normal user trust review.
- Scope confirmed: only the dashboard and FSA requests in this conversation; Keep Connect ASR implementation is excluded.

Validation: 295 task tests passed in the isolated snapshot; 92 Codex integration tests and 4 packaging tests passed. The 58 evidence tests also passed through the real task CLI. Two full-suite session-resolution fixtures fail on the host because they assume no real Codex ancestor; the isolated suite passed. Dashboard validation: 115 frontend and 25 HTTP tests passed; live routing, refresh, browser navigation and card containment verified.
