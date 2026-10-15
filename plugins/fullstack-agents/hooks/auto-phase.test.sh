#!/usr/bin/env bash
# Self-check for automatic dashboard phases. Run: bash hooks/auto-phase.test.sh
set -uo pipefail

hook="$(cd "$(dirname "$0")" && pwd)/auto-phase"
tb="$(cd "$(dirname "$0")" && pwd)/../scripts/team-board"
fail=0
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
export FSA_TEAM_BOARD="$tmp/board.json"
unset FSA_DONE_BRANCHES

git init -q --bare -b main "$tmp/origin.git"
git init -q -b main "$tmp/repo"
git -C "$tmp/repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
git -C "$tmp/repo" remote add origin "$tmp/origin.git"
git -C "$tmp/repo" push -q -u origin main 2>/dev/null
git -C "$tmp/repo" remote set-head origin main >/dev/null 2>&1

phase() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["phases"].get("s1", {}).get("phase", "none"))' "$FSA_TEAM_BOARD" 2>/dev/null || echo none; }
reset() { rm -f "$FSA_TEAM_BOARD"; [ -z "${1:-}" ] || python3 "$tb" --session s1 phase "$1" >/dev/null; }
push() {  # command stderr [interrupted]
    python3 -c 'import json,sys; print(json.dumps({"session_id": "s1", "cwd": sys.argv[1], "tool_input": {"command": sys.argv[2]},
        "tool_response": {"stdout": "", "stderr": sys.argv[3], "interrupted": sys.argv[4] == "1"}}))' "$tmp/repo" "$1" "${2:-}" "${3:-0}" | bash "$hook" push
}
prompt() {
    python3 -c 'import json,sys; print(json.dumps({"session_id": "s1", "cwd": sys.argv[1], "prompt": sys.argv[2]}))' "$tmp/repo" "$1" | bash "$hook" prompt
}
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1 (want $3, got $2)"; fail=1; fi; }

reset investigate; push "git push origin main" "To origin.git
   a..b  main -> main"
check "push from default branch -> complete" "$(phase)" complete
reset investigate; push "cd /x && git -C . push -q" ""
check "push with global flags -> complete" "$(phase)" complete
reset investigate; push "git push origin main" " ! [rejected]        main -> main (fetch first)
error: failed to push some refs"
check "rejected push -> unchanged" "$(phase)" investigate
reset investigate; push "git push --dry-run" ""
check "dry run -> unchanged" "$(phase)" investigate
reset investigate; push "git push" "" 1
check "interrupted push -> unchanged" "$(phase)" investigate
reset investigate; push "git status && echo push" ""
check "not a push -> unchanged" "$(phase)" investigate
git -C "$tmp/repo" checkout -q -b feature
reset investigate; push "git push -u origin feature" ""
check "feature branch push -> unchanged" "$(phase)" investigate
FSA_DONE_BRANCHES="dev,feature" push "git push" ""
check "FSA_DONE_BRANCHES branch -> complete" "$(phase)" complete
git -C "$tmp/repo" checkout -q main

reset complete; prompt "add a create button to the list"
check "prompt after complete -> investigate" "$(phase)" investigate
reset review; prompt "looks good, now fix the header"
check "prompt after review -> investigate" "$(phase)" investigate
reset implement; prompt "also rename the column"
check "prompt mid-build -> unchanged" "$(phase)" implement
reset complete; prompt "<task-notification><status>completed</status></task-notification>"
check "notification -> unchanged" "$(phase)" complete
reset; prompt "first request"
check "no declared phase -> unchanged" "$(phase)" none

exit "$fail"
