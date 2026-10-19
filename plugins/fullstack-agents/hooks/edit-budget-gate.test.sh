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
process.stdout.write(JSON.stringify({tool_name:"Edit",tool_input:{file_path:process.argv[1]}}));
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

echo "--- P5: per-session budget (session_id present) ---"
export FSA_STATE_HOME="$T/state"
sess() {  # mode session path -> exit code
  node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({session_id:process.argv[2],tool_name:"Edit",tool_input:{file_path:process.argv[1]}}))' "$R/$3" "$2" \
    | bash "$H" $([ "$1" = record ] && echo record) >/dev/null 2>&1; echo $?; }
edit_ok() {  # session path: a successful edit = gate allows, file changes, PostToolUse records
  [ "$(sess check "$1" "$2")" = 0 ] || return 1; dirty "$2"; sess record "$1" "$2" >/dev/null; }
scheck() { want=$1; got=$(sess check "$2" "$3"); if [ "$got" = "$want" ]; then echo "ok   ($got) $4"; else echo "FAIL want=$want got=$got :: $4"; FAILED=1; fi; }
reset_tree; noenv; rm -rf "$T/state"; write_conf
dirty src/o1.rs src/o2.ts src/o3.tsx src/o4.rs src/o5.rs   # another session's uncommitted work
scheck 0 A src/a.rs "other sessions' 5 dirty files spend nothing"
edit_ok A src/a.rs; edit_ok A src/b.ts; edit_ok A src/c.tsx
scheck 2 A src/d.rs "4th new path for session A, 3 recorded and open"
scheck 0 A src/b.ts "re-edit of a recorded open path is free"
scheck 0 B src/d.rs "session B is isolated from A's count"
scheck 2 A src/o1.rs "another session's dirty file is a NEW path for A, and A is at its limit"
echo "--- refused attempts are never recorded ---"
scheck 2 A src/e.rs "refused"
n=$(grep -c . "$T/state/edit-budget/A.paths"); [ "$n" = 3 ] && echo "ok   ledger holds 3 successful edits" || { echo "FAIL ledger has $n"; FAILED=1; }
echo "--- committing what is done frees the budget ---"
git -C "$R" add src/a.rs src/b.ts src/c.tsx && git -C "$R" commit -qm done
scheck 0 A src/d.rs "after commit the recorded paths are clean"
echo "--- resume keeps the count (same session id, new hook processes) ---"
edit_ok A src/f.rs; edit_ok A src/g.rs; edit_ok A src/h.rs
scheck 2 A src/i.rs "resumed session still at limit"
echo "--- carve-outs still refuse a session, record mode never refuses ---"
scheck 2 A services/rustpbx/src/z.rs "carve-out with a session id"
got=$(sess record A services/rustpbx/src/z.rs); [ "$got" = 0 ] && echo "ok   (0) record mode never blocks" || { echo "FAIL record blocked"; FAILED=1; }
echo "--- concurrent records from parallel tool calls keep every path ---"
rm -rf "$T/state"; for i in $(seq 1 12); do (dirty "src/p$i.rs"; sess record C "src/p$i.rs" >/dev/null) & done; wait
n=$(sort -u "$T/state/edit-budget/C.paths" | grep -c .); [ "$n" = 12 ] && echo "ok   12 concurrent records" || { echo "FAIL concurrent records: $n"; FAILED=1; }
echo "--- an unwritable ledger falls back to the whole-tree count, never to zero ---"
reset_tree; rm -rf "$T/state"; mkdir -p "$T/state/edit-budget"; chmod 500 "$T/state/edit-budget"
dirty src/q1.rs src/q2.rs src/q3.rs src/q4.rs src/q5.rs
scheck 2 D src/q6.rs "unwritable ledger: 5 dirty gated files count"
chmod 700 "$T/state/edit-budget"
echo "--- an unparseable conf refuses instead of switching the gate off ---"
reset_tree; printf 'edit_budget=5\n\377\376\n' > "$R/.claude/fsa-team.conf"
msg=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({session_id:"E",tool_input:{file_path:process.argv[1]}}))' "$R/services/rustpbx/x.rs" | bash "$H" 2>&1 >/dev/null); got=$?
if [ "$got" = 2 ] && printf '%s' "$msg" | grep -q 'could not be parsed'; then echo "ok   (2) unparseable conf refuses"; else echo "FAIL unparseable conf: $got $msg"; FAILED=1; fi
write_conf
unset FSA_STATE_HOME

echo
if [ "$FAILED" = 0 ]; then echo "ALL PASS"; else echo "FAILURES PRESENT"; fi
exit "$FAILED"
