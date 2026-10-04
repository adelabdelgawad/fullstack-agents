#!/usr/bin/env bash
# Tests for hooks/team-guard and hooks/session-end against a throwaway board.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TB="${HERE}/../scripts/team-board"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export FSA_TEAM_BOARD="$TMP/board.json"
PASS=0; FAIL=0
ok() { if [ "$1" = "true" ]; then PASS=$((PASS+1)); echo "ok   $2"; else FAIL=$((FAIL+1)); echo "FAIL $2 ($3)"; fi; }
guard() { printf '{"session_id":"%s","cwd":"%s","tool_input":{"command":"%s"}}' "$1" "$TMP" "$2" | bash "$HERE/team-guard" 2>"$TMP/err"; }

unset FSA_TEAM_DEPLOY_REGEX
out=$(guard A "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 0 ] && [ -z "$out" ] && echo true)" "no deploy pattern configured is a no-op" "rc=$rc out=$out"

export FSA_TEAM_DEPLOY_REGEX='deploy-backend\.sh|compose .*up'
out=$(guard A "ls -la"); rc=$?
ok "$([ $rc -eq 0 ] && [ -z "$out" ] && echo true)" "a non-deploy command passes silently" "rc=$rc"

out=$(guard A "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 0 ] && echo "$out" | grep -q 'hold the board' && echo true)" "a deploy with no lock passes with a reminder" "rc=$rc out=$out"

"$TB" --session B lock deploy --name beta --reason "engine deploy"
out=$(guard A "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 2 ] && grep -q 'held by beta' "$TMP/err" && echo true)" "a peer's live deploy lock blocks" "rc=$rc"

out=$(guard B "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "the lock holder's own deploy passes" "rc=$rc"

out=$(FSA_TEAM_GATE_OFF=1 guard A "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "the user override passes" "rc=$rc"

"$TB" --session B lock deploy --name beta --reason short --ttl 0
out=$(guard A "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "an expired lock does not block" "rc=$rc"

printf 'not json' | bash "$HERE/team-guard"; ok "$([ $? -eq 0 ] && echo true)" "malformed hook input passes" ""

"$TB" --session B lock deploy --name beta --reason again
printf '{"session_id":"B","cwd":"%s"}' "$TMP" | bash "$HERE/session-end"
out=$(guard A "scripts/deploy-backend.sh"); rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "session-end releases the ending session's lock" "rc=$rc"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
