#!/usr/bin/env bash
# Tests for scripts/team-board: claims, expiring locks, malformed boards and concurrent writers.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TB="${HERE}/../scripts/team-board"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export FSA_TEAM_BOARD="$TMP/board.json"
PASS=0; FAIL=0
ok() { if [ "$1" = "true" ]; then PASS=$((PASS+1)); echo "ok   $2"; else FAIL=$((FAIL+1)); echo "FAIL $2 ($3)"; fi; }

out=$("$TB" --session A status); ok "$([ "$out" = "board empty" ] && echo true)" "no board reads as empty" "$out"
"$TB" --session A check-lock deploy; ok "$([ $? -eq 0 ] && echo true)" "no board never blocks" ""

"$TB" --session A claim --name alpha --task "messaging phase 2" --scope "src/backend"
out=$("$TB" --session B status); ok "$(echo "$out" | grep -q 'CLAIM alpha: messaging phase 2 \[src/backend\]' && echo true)" "claim is visible to peers" "$out"

"$TB" --session A lock deploy --name alpha --reason "drained backend deploy"
"$TB" --session B check-lock deploy >/dev/null; rc=$?
ok "$([ $rc -eq 3 ] && echo true)" "a peer's live lock blocks" "rc=$rc"
"$TB" --session A check-lock deploy; ok "$([ $? -eq 0 ] && echo true)" "own lock does not block" ""
"$TB" --session B lock deploy --name beta --reason x >/dev/null; rc=$?
ok "$([ $rc -eq 3 ] && echo true)" "cannot take a lock a peer holds" "rc=$rc"
"$TB" --session B unlock deploy
"$TB" --session B check-lock deploy >/dev/null; ok "$([ $? -eq 3 ] && echo true)" "a peer cannot unlock someone else's lock" ""

"$TB" --session A lock deploy --name alpha --reason short --ttl 0
"$TB" --session B check-lock deploy; ok "$([ $? -eq 0 ] && echo true)" "an expired lock never blocks" ""
"$TB" --session B lock deploy --name beta --reason "now mine"; ok "$([ $? -eq 0 ] && echo true)" "an expired lock can be taken" ""

"$TB" release-session B
"$TB" --session A check-lock deploy; ok "$([ $? -eq 0 ] && echo true)" "release-session drops that session's locks" ""

"$TB" --session A note --name alpha "deployed abc123; adds no migration"
out=$("$TB" --session C status); ok "$(echo "$out" | grep -q 'EVENT .* alpha: deployed abc123' && echo true)" "notes reach the event log" "$out"

"$TB" --session A phase audit --worktree /tmp/wt-a --note "u1 returned"
"$TB" --session A phase review
out=$("$TB" --session C status --json | python3 -c 'import json,sys; v=json.load(sys.stdin)["phases"]["A"]; print(v["phase"], v["worktree"])')
ok "$([ "$out" = "review /tmp/wt-a" ] && echo true)" "phase records the latest phase and keeps the declared worktree" "$out"
"$TB" --session A phase merged 2>/dev/null; ok "$([ $? -ne 0 ] && echo true)" "phase rejects a phase the dashboard derives itself" ""

steps() { "$TB" --session C status --json | python3 -c 'import json,sys; print(" ".join(i["text"] + "=" + i["state"] for i in json.load(sys.stdin)["steps"]["A"]["items"]))'; }
"$TB" --session A steps set "find cause" "plan fix"
"$TB" --session A steps active 1
"$TB" --session A steps done 1 --note "found it"
"$TB" --session A steps add "write brief"
"$TB" --session A steps active 2
ok "$([ "$(steps)" = "find cause=done plan fix=active write brief=pending" ] && echo true)" "steps record add, active and done" "$(steps)"
"$TB" --session A steps set "plan fix" "ship"
ok "$([ "$(steps)" = "plan fix=active ship=pending" ] && echo true)" "set keeps the state of a step whose text is unchanged" "$(steps)"
"$TB" --session A steps done 9 2>/dev/null; ok "$([ $? -eq 2 ] && echo true)" "a step number out of range is refused" ""
"$TB" --session A phase plan
ok "$([ "$(steps)" = "plan fix=active ship=pending" ] && echo true)" "a phase change keeps the steps" "$(steps)"

"$TB" --session A wait "approve the staged plan"
out=$("$TB" --session C status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["waits"]["A"]["need"])')
ok "$([ "$out" = "approve the staged plan" ] && echo true)" "wait records what the session needs" "$out"
"$TB" --session A wait 2>/dev/null; ok "$([ $? -eq 2 ] && echo true)" "wait without a need is refused" ""
"$TB" --session A wait --clear
out=$("$TB" --session C status --json | python3 -c 'import json,sys; print("A" in json.load(sys.stdin)["waits"])')
ok "$([ "$out" = "False" ] && echo true)" "wait --clear removes it" "$out"

echo '{not json' > "$FSA_TEAM_BOARD"
"$TB" --session B check-lock deploy 2>/dev/null; ok "$([ $? -eq 0 ] && echo true)" "a malformed board never blocks" ""
"$TB" --session B claim --name beta --task recover 2>/dev/null
out=$("$TB" --session B status --json); ok "$(echo "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("true" if "B" in d["claims"] else "")')" "a malformed board is rewritten on the next write" ""

rm -f "$FSA_TEAM_BOARD"
for i in $(seq 1 25); do "$TB" --session "S$i" claim --name "s$i" --task "t$i" & done; wait
n=$("$TB" --session X status --json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["claims"]))')
ok "$([ "$n" = 25 ] && echo true)" "25 concurrent writers lose no claim" "claims=$n"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
