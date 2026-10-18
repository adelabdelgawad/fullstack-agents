#!/usr/bin/env bash
# Battery for edit-budget-gate: replays the UCM gate-codex-implement.sh budget/carve-out cases, plus the plugin's
# own on/off and override cases. Skipped (now covered by run-owner-gate.test.sh, not this gate): every UCM case
# about a live/finished/wedged/dead Codex run owning a path, the per-run ALLOWED_PATHS cases, and the registry
# directory-scanning cases (D5) — live-run ownership is plugins/fullstack-agents/hooks/run-owner-gate.
set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/edit-budget-gate"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME"
unset FSA_IMPLEMENTER_RUN FSA_SKIP_EDIT_BUDGET KC_CODEX_GATE_OFF KC_DIRECT_EDIT_LIMIT
R="$T/r e p o"; mkdir -p "$R/.claude"
git -C "$R" init -q
git -C "$R" config user.email t@t
git -C "$R" config user.name t
echo seed > "$R/seed.txt"
git -C "$R" add seed.txt
git -C "$R" commit -qm seed

carve_outs='services/* *migrations/* src/backend/*worker/*.rs src/backend/*workers/*.rs src/backend/*worker.rs src/backend/*workers.rs src/backend/*/recovery/*.rs src/backend/*recovery.rs src/backend/*/lifecycle/*.rs src/backend/*lifecycle.rs src/backend/*leader_election.rs src/backend/*/sweeper/*.rs src/backend/*sweeper.rs src/backend/*_consumer.rs'
write_conf() { printf 'edit_budget=3\ngated_extensions=rs ts tsx\ncarve_outs=%s\n' "$carve_outs" > "$R/.claude/fsa-team.conf"; }
write_conf

dirty() { for f in "$@"; do mkdir -p "$(dirname "$R/$f")"; echo x > "$R/$f"; done; }
reset_tree() { find "$R" -mindepth 1 -type f ! -name seed.txt -not -path '*/.git/*' -not -path '*/.claude/*' -delete; }

run() { node -e '
process.stdout.on("error",()=>{});
process.stdout.write(JSON.stringify({session_id:"s",tool_name:"Edit",tool_input:{file_path:process.argv[1]}}));
' "$R/$1" | KC_DIRECT_EDIT_LIMIT="${LIM:-}" bash "$H" >/dev/null 2>&1; echo $?; }
check() { want=$1; got=$(run "$2"); if [ "$got" = "$want" ]; then echo "ok   ($got) $3"; else echo "FAIL want=$want got=$got :: $3"; FAILED=1; fi; }

FAILED=0
noenv() { unset LIM; }
noenv; reset_tree
echo "--- non-source is never gated (0) ---"
check 0 docs/a.md        "markdown"
check 0 migrations/1.sql "sql migration"
check 0 Cargo.toml       "manifest"

echo "--- risk carve-outs always block (2) ---"
check 2 services/rustpbx/src/a.rs                "vendored fork"
check 2 src/backend/crates/x/migrations/m.rs     "migration dir"
check 2 tests-migrations/m.rs                    "tests-migrations dir"
check 2 src/backend/crates/pbx-worker/a.rs       "worker"
check 2 src/backend/crates/x/recovery.rs         "recovery"
check 2 src/backend/crates/x/leader_election.rs  "leader"
check 2 src/backend/apps/pbx-realtime/src/call_consumer.rs "backend consumer"

echo "--- budget: under limit allows (0) ---"
reset_tree; noenv
check 0 src/a.rs "first file, nothing dirty"
dirty src/a.rs src/b.ts
check 0 src/c.tsx "third file, 2 already open"

echo "--- budget: at limit blocks (2) ---"
reset_tree; dirty src/a.rs src/b.ts src/c.tsx
check 2 src/d.rs "fourth NEW file, 3 already open"

echo "--- re-editing an already-open file is free (0) ---"
check 0 src/a.rs "re-edit one of the 3"

echo "--- carve-outs must NOT over-block ordinary files (0) ---"
reset_tree; noenv
check 0 src/frontend/features/queue/consumer-view.tsx   "frontend component named consumer"
check 0 src/frontend/app/recovery/page.tsx              "frontend route named recovery"
check 0 src/frontend/lib/worker-status.ts               "frontend helper named worker"
check 0 src/backend/crates/pbx-dtos/src/migration_dto.rs "backend dto, not a migration dir"

echo "--- limit is configurable (legacy KC_DIRECT_EDIT_LIMIT overrides edit_budget) ---"
reset_tree; dirty src/a.rs; noenv
LIM=1 check 2 src/zz.ts "limit=1, one file already open"
LIM=9 check 0 src/zz.ts "limit=9"

echo "--- gate off when unconfigured ---"
reset_tree; dirty src/a.rs src/b.ts src/c.tsx; noenv
rm -f "$R/.claude/fsa-team.conf"
check 0 src/d.rs "no edit_budget, no carve_outs: gate does nothing"
reset_tree
printf 'edit_budget=3\ngated_extensions=rs ts tsx\n' > "$R/.claude/fsa-team.conf"
check 0 services/rustpbx/x.rs "no carve_outs configured: carve-out path is not refused"
write_conf

echo "--- invalid conf value refuses, naming the key ---"
reset_tree; noenv
printf 'edit_budget=not-a-number\ncarve_outs=%s\n' "$carve_outs" > "$R/.claude/fsa-team.conf"
msg=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({tool_input:{file_path:process.argv[1]}}))' "$R/src/a.rs" | bash "$H" 2>&1 >/dev/null); got=$?
if [ "$got" = 2 ] && printf '%s' "$msg" | grep -q edit_budget; then echo "ok   (2) invalid edit_budget refuses and names the key"; else echo "FAIL want=2/edit_budget got=$got :: $msg"; FAILED=1; fi
write_conf

echo "--- FSA_SKIP_EDIT_BUDGET disables only this gate ---"
reset_tree; dirty src/a.rs src/b.ts src/c.tsx
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({tool_input:{file_path:process.argv[1]}}))' "$R/src/d.rs" | FSA_SKIP_EDIT_BUDGET=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) FSA_SKIP_EDIT_BUDGET=1 bypasses" || { echo "FAIL want=0 got=$got :: FSA_SKIP_EDIT_BUDGET"; FAILED=1; }

echo "--- legacy KC_CODEX_GATE_OFF disables this gate too ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({tool_input:{file_path:process.argv[1]}}))' "$R/services/rustpbx/x.rs" | KC_CODEX_GATE_OFF=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) KC_CODEX_GATE_OFF=1 bypasses" || { echo "FAIL want=0 got=$got :: override"; FAILED=1; }

echo "--- a dispatched implementer run is skipped entirely (its own fence governs it) ---"
reset_tree; dirty src/a.rs src/b.ts src/c.tsx
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({tool_input:{file_path:process.argv[1]}}))' "$R/services/rustpbx/x.rs" | FSA_IMPLEMENTER_RUN=implement-x bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) FSA_IMPLEMENTER_RUN skips the gate" || { echo "FAIL want=0 got=$got :: implementer run"; FAILED=1; }

echo "--- a repository path containing a space ---"
reset_tree; noenv
check 2 services/rustpbx/src/a.rs "carve-out inside a spaced repo path"

echo
if [ "$FAILED" = 0 ]; then echo "ALL PASS"; else echo "FAILURES PRESENT"; fi
exit "$FAILED"
