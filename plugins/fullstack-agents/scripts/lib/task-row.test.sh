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
python3 -I "$fsa_task_lib/task_tracking.py" init --format legacy --root "$root" --file "$ledger" --task 'S4a|pending|Existing title|Keep me' > /dev/null

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
case "$err" in "fullstack-agents: task ledger unreadable; ledger updates disabled for this run: "*) chk "the warning says the ledger is unreadable and disabled" ok ok ;; *) chk "the warning says the ledger is unreadable and disabled" warning "$err" ;; esac

badledger=docs/tasks/bad.md
printf '%s\n' '# Bad' '<!-- fsa:tasks:start -->' '| Bad | Header | Cols | Here |' '| --- | --- | --- | --- |' '<!-- fsa:tasks:end -->' > "$root/$badledger"
b=$(brief "TASK: $badledger#Z1")
fsa_task_row_init "$b" "$root"; before=$(cat "$root/$badledger")
cat > "$tmp/malformed.sh" <<SCRIPT
set -euo pipefail
source "$fsa_task_lib/task-row.sh"
export FSA_TASKS_DIR="$FSA_TASKS_DIR" CODEX_THREAD_ID="$CODEX_THREAD_ID"
fsa_task_row_init "$b" "$root"
fsa_task_row_dispatch codex unit-b run-bad
fsa_task_row_renew codex unit-b
fsa_task_row_finish succeeded run-bad
echo reached
SCRIPT
out=$(bash "$tmp/malformed.sh" 2>&1)
chk "set -euo pipefail reaches the next line after a malformed v2 ledger" "reached" "$(tail -1 <<<"$out")"
chk "a malformed v2 ledger is left byte-for-byte unchanged" "$before" "$(cat "$root/$badledger")"
case "$out" in *"task ledger unreadable; ledger updates disabled for this run: "*"Task table header"*) chk "the malformed ledger warns with the parser's reason" ok ok ;; *) chk "the malformed ledger warns with the parser's reason" warning "$out" ;; esac

v2ledger=docs/tasks/v2.md
python3 -I "$fsa_task_lib/task_tracking.py" init --format legacy --root "$root" --file "$v2ledger" \
  --task 'V1|pending|V2 task|' --task 'Vdone|done|Finished|' > /dev/null
python3 -I "$fsa_task_lib/task_tracking.py" upgrade --root "$root" --file "$v2ledger" > /dev/null
ledger=$v2ledger
b=$(brief "TASK: $v2ledger#V1")
fsa_task_row_init "$b" "$root"; fsa_task_row_dispatch codex unit-b run-v2; fsa_task_row_finish succeeded run-v2
chk "v2 success moves the row to verifying" "verifying lead succeeded: awaiting lead audit (run run-v2)" "$(row V1 '"\(.status) \(.owner) \(.note)"')"
b=$(brief "TASK: $v2ledger#missing")
fsa_task_row_init "$b" "$root"; before=$(cat "$root/$v2ledger")
warning=$(fsa_task_row_dispatch codex unit-b run-missing 2>&1)
chk "v2 missing row is not added" "$before" "$(cat "$root/$v2ledger")"
case "$warning" in *"add the row first"*) chk "v2 missing row warns" ok ok ;; *) chk "v2 missing row warns" warning "$warning" ;; esac
b=$(brief "TASK: $v2ledger#Vdone")
fsa_task_row_init "$b" "$root"; before=$(cat "$root/$v2ledger")
fsa_task_row_dispatch codex unit-b run-done 2>/dev/null
fsa_task_renewed=$((SECONDS - 300)); fsa_task_row_renew codex unit-b
fsa_task_row_finish succeeded run-done 2>/dev/null
chk "v2 done row is untouched" "$before" "$(cat "$root/$v2ledger")"

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
