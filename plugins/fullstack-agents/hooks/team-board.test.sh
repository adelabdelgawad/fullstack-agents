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

TASKS_ROOT="$TMP/tasks-root"
mkdir -p "$TASKS_ROOT"
export FSA_TASKS_DIR="$TMP/tasks-state"
FT="${HERE}/../scripts/fsa-task"
( cd "$TASKS_ROOT" && python3 "$FT" init --root . --file work.md --session T --format v2 --task 'S1|pending|work|' >/dev/null )
( cd "$TASKS_ROOT" && "$TB" --session T phase complete 2>/dev/null ); rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "phase complete refused with an open v2 row" "rc=$rc"
( cd "$TASKS_ROOT" && python3 "$FT" set --root . --file work.md --session T --id S1 --status skipped >/dev/null )
( cd "$TASKS_ROOT" && "$TB" --session T phase complete >/dev/null 2>&1 ); rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "phase complete accepted once the v2 ledger is done" "rc=$rc"
( cd "$TASKS_ROOT" && python3 "$FT" init --root . --file legacy.md --session L --format legacy --task 'S1|pending|work|' >/dev/null )
( cd "$TASKS_ROOT" && "$TB" --session L phase complete 2>/dev/null ); rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "phase complete refused with an open legacy row" "rc=$rc"
( cd "$TASKS_ROOT" && "$TB" --session nobind phase complete >/dev/null 2>&1 ); rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "phase complete unchanged for a session without a ledger" "rc=$rc"

export FSA_TEAM_BOARD="$TMP/msg.json"
"$TB" --session AAAA1111aaaa claim --name alpha --task a >/dev/null
"$TB" --session BBBB2222bbbb claim --name beta --task b >/dev/null
"$TB" --session CCCC3333cccc claim --name beta --task c >/dev/null
id=$("$TB" --session AAAA1111aaaa send --to BBBB2222bbbb --act request "please   rebase
on main")
ok "$([ "$id" = m1 ] && echo true)" "send prints the message id" "$id"
out=$("$TB" --session BBBB2222bbbb inbox)
ok "$(echo "$out" | grep -q '^m1 from alpha (AAAA1111), request, hop 1: please rebase on main$' && echo true)" "a direct message reaches its recipient as one line" "$out"
out=$("$TB" --session BBBB2222bbbb inbox)
ok "$([ "$out" = "no unread messages" ] && echo true)" "the cursor advances past read messages" "$out"
out=$("$TB" --session CCCC3333cccc inbox)
ok "$([ "$out" = "no unread messages" ] && echo true)" "a direct message stays with its recipient" "$out"
"$TB" --session AAAA1111aaaa send --to all --act inform "deploy at noon" >/dev/null
out=$("$TB" --session CCCC3333cccc inbox); ok "$(echo "$out" | grep -q 'inform, hop 1: deploy at noon' && echo true)" "a broadcast reaches every peer" "$out"
out=$("$TB" --session AAAA1111aaaa inbox); ok "$([ "$out" = "no unread messages" ] && echo true)" "a broadcast skips its sender" "$out"
id=$("$TB" --session BBBB2222bbbb send --reply-to m1 --act done "rebased")
out=$("$TB" --session AAAA1111aaaa inbox)
ok "$(echo "$out" | grep -q "^$id from beta (BBBB2222), done, hop 2, re m1: rebased$" && echo true)" "--to defaults to the sender of the replied message" "$out"
"$TB" --session BBBB2222bbbb send --to beta --act inform x 2>/dev/null; rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "a name shared by two sessions is refused" "rc=$rc"
"$TB" --session BBBB2222bbbb send --to BBBB2222 --act inform x 2>/dev/null; rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "a session cannot message itself" "rc=$rc"
"$TB" --session BBBB2222bbbb send --to alpha --act inform "by name" >/dev/null; rc=$?
ok "$([ $rc -eq 0 ] && echo true)" "a unique claim name resolves" "rc=$rc"
"$TB" --session BBBB2222bbbb send --reply-to m99 --act done x 2>/dev/null; rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "an unknown reply-to is refused" "rc=$rc"
"$TB" --session BBBB2222bbbb send --to nobody --act inform x 2>/dev/null; rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "an unknown recipient is refused" "rc=$rc"
prev=$("$TB" --session AAAA1111aaaa send --to BBBB2222bbbb --act request "hop chain")
for i in 2 3 4 5 6; do
    s=$([ $((i % 2)) -eq 0 ] && echo BBBB2222bbbb || echo AAAA1111aaaa)
    prev=$("$TB" --session "$s" send --reply-to "$prev" --act inform "hop $i") || break
done
hops=$("$TB" --session X status --json | python3 -c "import json,sys; print([m['hops'] for m in json.load(sys.stdin)['messages'] if m['id']=='$prev'][0])")
ok "$([ "$hops" = 6 ] && echo true)" "a reply chain reaches hop 6" "hops=$hops"
"$TB" --session AAAA1111aaaa send --reply-to "$prev" --act inform "hop 7" 2>/dev/null; rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "hop 7 is refused" "rc=$rc"

"$TB" --session AAAA1111aaaa send --to all --act inform "old news" >/dev/null
"$TB" --session AAAA1111aaaa send --to DDDD4444dddd --act request "direct for new" 2>/dev/null; rc=$?
ok "$([ $rc -eq 2 ] && echo true)" "a session the board never saw cannot be addressed" "rc=$rc"
"$TB" --session DDDD4444dddd claim --name delta --task d >/dev/null
"$TB" --session AAAA1111aaaa send --to delta --act request "direct for new" >/dev/null
python3 - "$FSA_TEAM_BOARD" <<'PY'
import json, sys, datetime as dt
p = sys.argv[1]; d = json.load(open(p))
old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
for m in d["messages"]:
    if m["text"] in ("old news", "direct for new"):
        m["at"] = old
json.dump(d, open(p, "w"))
PY
out=$("$TB" --session DDDD4444dddd inbox)
ok "$(echo "$out" | grep -q 'direct for new' && ! echo "$out" | grep -q 'old news' && echo true)" "a new cursor takes old direct messages but skips old broadcasts" "$out"
"$TB" --session GGGG7777gggg claim --name golf --task g >/dev/null
"$TB" --session AAAA1111aaaa send --to golf --act request "direct first" >/dev/null
"$TB" --session AAAA1111aaaa send --to all --act inform "late old broadcast" >/dev/null
python3 - "$FSA_TEAM_BOARD" <<'PY'
import json, sys, datetime as dt
p = sys.argv[1]; d = json.load(open(p))
old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
for m in d["messages"]:
    if m["text"] in ("direct first", "late old broadcast"):
        m["at"] = old
json.dump(d, open(p, "w"))
PY
"$TB" --session GGGG7777gggg inbox >/dev/null
out=$("$TB" --session GGGG7777gggg inbox)
ok "$([ "$out" = "no unread messages" ] && echo true)" "a skipped old broadcast never arrives on a later read" "$out"

"$TB" --session AAAA1111aaaa send --to all --act inform "survives old writers" >/dev/null
git -C "$HERE" show ae040f6:plugins/fullstack-agents/scripts/team-board > "$TMP/old-team-board" 2>/dev/null && chmod +x "$TMP/old-team-board"
python3 "$TMP/old-team-board" --session EEEE5555eeee claim --name echo --task e
n=$("$TB" --session X status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(m["text"]=="survives old writers" for m in d["messages"]), d["msg_seq"]>0)')
ok "$([ "$n" = "1 True" ] && echo true)" "a claim by the previous release keeps the messages" "$n"

PI="${HERE}/peer-inbox"
export TMPDIR="$TMP/state"; mkdir -p "$TMPDIR"
hook() { printf '{"session_id":"%s","hook_event_name":"%s","cwd":"%s"%s}' "$1" "$2" "$TMP" "${3:-}" | "$PI"; }
rm -f "$FSA_TEAM_BOARD.msg"
"$TB" --session FFFF6666ffff claim --name fox --task f >/dev/null
out=$(hook FFFF6666ffff PostToolUse)
ok "$([ -z "$out" ] && echo true)" "peer-inbox is silent without a send sentinel" "$out"
"$TB" --session AAAA1111aaaa send --to fox --act request "check the lock" >/dev/null
out=$(hook FFFF6666ffff PostToolUse ',"agent_id":"sub1"')
ok "$([ -z "$out" ] && echo true)" "peer-inbox skips subagent calls" "$out"
out=$(hook FFFF6666ffff UserPromptSubmit)
ev=$(printf '%s' "$out" | python3 -c 'import json,sys; h=json.load(sys.stdin)["hookSpecificOutput"]; print(h["hookEventName"], "check the lock" in h["additionalContext"], "never user approval" in h["additionalContext"])' 2>/dev/null)
ok "$([ "$ev" = "UserPromptSubmit True True" ] && echo true)" "peer-inbox delivers unread messages for the hook event" "$ev / $out"
out=$(hook FFFF6666ffff PostToolUse)
ok "$([ -z "$out" ] && echo true)" "peer-inbox delivers a message once" "$out"
touch -d '2 days ago' "$FSA_TEAM_BOARD.msg"
rm -f "$TMPDIR/fullstack-agents-state/inbox-FFFF6666ffff.stamp"
hook FFFF6666ffff PostToolUse >/dev/null
before=$(stat -c %Y "$FSA_TEAM_BOARD"); sleep 1
hook FFFF6666ffff PostToolUse >/dev/null
after=$(stat -c %Y "$FSA_TEAM_BOARD")
ok "$([ "$before" = "$after" ] && echo true)" "an old sentinel does not start the board on every call" "$before vs $after"
out=$(FSA_PEER_INBOX=off hook AAAA1111aaaa PostToolUse)
ok "$([ -z "$out" ] && echo true)" "FSA_PEER_INBOX=off disables peer-inbox" "$out"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
