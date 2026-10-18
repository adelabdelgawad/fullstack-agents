#!/usr/bin/env bash
# Battery for run-owner-gate: run after any edit to the hook.
set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run-owner-gate"
T=$(mktemp -d); trap 'kill $marked 2>/dev/null; rm -rf "$T"' EXIT
export HOME="$T/home"; unset FSA_CODEX_RUNS_DIR FSA_IMPLEMENTER_RUN FSA_SKIP_RUN_GATE
R="$T/repo"; RUNS="$T/runs"; LEG="$T/legacy"; mkdir -p "$R/.claude" "$RUNS" "$LEG" "$R/src"
git -C "$R" init -q
printf 'runs_dir=%s\nlegacy_runs_dirs=%s\n' "$RUNS" "$LEG" > "$R/.claude/fsa-team.conf"
run() { printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$R/$1" | bash "$H" >/dev/null 2>&1; echo $?; }
FAILED=0
check() { got=$(run "$2"); if [ "$got" = "$1" ]; then echo "ok   ($got) $3"; else echo "FAIL want=$1 got=$got :: $3"; FAILED=1; fi; }
v2() { printf '%s\n' "$3" > "$1/$2.allow"; : > "$1/$2.log"
  jq -n --arg id "$2" --arg r "$R" '{id:$id,schema:2,engine:"codex",root:$r,cwd:$r}' > "$1/$2.meta.json"; }
v1() { printf '%s\n' "$3" > "$1/$2.allow"; : > "$1/$2.log"; jq -n --arg r "$R" '{root:$r}' > "$1/$2.meta.json"; }

check 0 src/a.rs "no run owns the path"
v1 "$RUNS" implement-1 src/a.rs
check 2 src/a.rs "v1 run with a fresh log and no result owns it"
: > "$RUNS/implement-1.last.txt"
check 0 src/a.rs "v1 run with a result releases it"
v2 "$LEG" implement-2 src/b.rs
FSA_RUN_ID=implement-2 setsid sleep 30 & marked=$!
sleep 0.3
check 2 src/b.rs "v2 run in a legacy dir with a live marked process owns it"
kill "$marked"; wait "$marked" 2>/dev/null
check 2 src/b.rs "v2 run with no engine record is uncertain and keeps it"
: > "$LEG/implement-2.released"
check 0 src/b.rs "explicitly released v2 run frees it"
v1 "$RUNS" implement-3 src/c.rs; jq -n '{root:"/elsewhere"}' > "$RUNS/implement-3.meta.json"
check 0 src/c.rs "a run of another repository never owns this repo's path"
v1 "$RUNS" implement-4 src/d.rs
got=$(printf '{"tool_input":{"file_path":"%s"}}' "$R/src/d.rs" | FSA_IMPLEMENTER_RUN=implement-4 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) the implementer run itself is not gated" || { echo "FAIL implementer gated"; FAILED=1; }
got=$(printf '{"tool_input":{"file_path":"%s"}}' "$R/src/d.rs" | FSA_SKIP_RUN_GATE=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) FSA_SKIP_RUN_GATE=1 bypasses" || { echo "FAIL override"; FAILED=1; }
got=$(printf '{"tool_input":{"file_path":"%s"}}' "$T/outside/x.rs" | bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) a path outside any repository is ignored" || { echo "FAIL outside path"; FAILED=1; }
echo; [ "$FAILED" = 0 ] && echo "ALL PASS" || echo "FAILURES PRESENT"
exit "$FAILED"
