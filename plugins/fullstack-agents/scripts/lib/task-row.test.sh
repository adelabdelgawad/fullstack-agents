#!/usr/bin/env bash
# Self-check for the dispatcher's TASK: row hooks and BUILD warning. Run: bash scripts/lib/task-row.test.sh
set -uo pipefail

source "$(dirname "$0")/task-row.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
root="$tmp/repo"
mkdir -p "$root/docs/tasks" "$root/.codex-briefs"
export FSA_TASKS_DIR="$tmp/state" CODEX_THREAD_ID=task-row-test
ledger=docs/tasks/work.md
python3 -I "$fsa_task_lib/task_tracking.py" init --root "$root" --file "$ledger" --task 'S4a|pending|Existing title|Keep me' > /dev/null

fail=0
chk() {
  if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1 (want '$2', got '$3')"; fail=1; fi
}
row() { python3 -I "$fsa_task_lib/task_tracking.py" show --json --root "$root" --file "$ledger" | jq -r --arg id "$1" ".items[] | select(.id == \$id) | $2"; }
brief() { printf '%s\n' "$@" > "$root/.codex-briefs/unit-b.md"; echo "$root/.codex-briefs/unit-b.md"; }

b=$(brief 'PLAN: none: test' 'BUILD: cargo check')
fsa_task_row_init "$b" "$root"; before=$(cat "$root/$ledger")
fsa_task_row_dispatch codex unit-b run-0; fsa_task_row_finish succeeded run-0
chk "no TASK line leaves the ledger untouched" "$before" "$(cat "$root/$ledger")"

b=$(brief "TASK: $ledger#S4b")
fsa_task_row_init "$b" "$root"
fsa_task_row_dispatch codex unit-b run-1
chk "a new row is added with the brief stem and an active engine lease" "unit-b in_progress codex implementing unit-b true" "$(row S4b '"\(.title) \(.status) \(.owner) \(.activity) \(.is_active)"')"
fsa_task_row_finish succeeded run-1
chk "success hands the row to the lead with the lease cleared" "in_progress lead  false succeeded: awaiting lead audit (run run-1)" "$(row S4b '"\(.status) \(.owner) \(.activity) \(.is_active) \(.note)"')"

b=$(brief "TASK: $root/$ledger#S4a")
fsa_task_row_init "$b" "$root"
fsa_task_row_dispatch claude unit-b run-2
chk "an existing row keeps its title and note at dispatch (absolute path)" "Existing title|Keep me|in_progress|claude" "$(row S4a '"\(.title)|\(.note)|\(.status)|\(.owner)"')"
fsa_task_row_finish scope_violation run-2
chk "a failed state blocks the row and names the run" "blocked scope_violation: see run run-2" "$(row S4a '"\(.status) \(.note)"')"

fsa_task_renewed=$((SECONDS - 300)); fsa_task_row_renew codex unit-b
chk "renewal after 240 s restores an active lease" "true" "$(row S4a .is_active)"

chk "the ledger path is relative to the run root" "$ledger" "$(fsa_task_row_relpath "$root")"
fsa_task_root="$tmp/elsewhere" fsa_task_file="$tmp/elsewhere/t.md"
chk "a ledger outside the run root has no relative path" "" "$(fsa_task_row_relpath "$root")"

b=$(brief "TASK: docs/tasks/missing.md#X1")
fsa_task_row_init "$b" "$root"
err=$( { fsa_task_row_dispatch codex unit-b run-3; fsa_task_row_finish succeeded run-3; echo "rc=$?"; } 2>&1 >/dev/null; )
rc=$( { fsa_task_row_dispatch codex unit-b run-3; fsa_task_row_finish succeeded run-3; echo "rc=$?"; } 2>/dev/null)
chk "a broken ledger only warns and never fails the caller" "rc=0" "$rc"
case "$err" in *"task ledger show for X1 failed"*) chk "the warning names the row" ok ok ;; *) chk "the warning names the row" warning "$err" ;; esac

b=$(brief "TASK: no-hash-here")
chk "a malformed TASK line warns and disables the hooks" "" "$(fsa_task_row_init "$b" "$root" 2>/dev/null; echo "$fsa_task_id")"

for line in 'BUILD: sg docker -c "cargo check"' 'BUILD: docker compose run app cargo check' 'BUILD: cd x && docker build .'; do
  b=$(brief "$line")
  chk "BUILD warns on: $line" "fullstack-agents: BUILD must run inside the implementer sandbox; drop sg/docker" "$(fsa_build_warn "$b" 2>&1)"
done
for line in 'BUILD: cargo check -p dockerize' 'BUILD: npx tsc --noEmit' 'NOTE: docker is forbidden'; do
  b=$(brief "$line")
  chk "BUILD stays quiet on: $line" "" "$(fsa_build_warn "$b" 2>&1)"
done

exit $fail
