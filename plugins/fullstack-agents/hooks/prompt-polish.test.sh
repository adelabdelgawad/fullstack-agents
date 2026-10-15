#!/usr/bin/env bash
# Self-check for prompt-polish skips. Run: bash hooks/prompt-polish.test.sh
set -uo pipefail

hook="$(cd "$(dirname "$0")" && pwd)/prompt-polish"
fail=0
export TMPDIR="$(mktemp -d)"; trap 'rm -rf "$TMPDIR"' EXIT

polish() {
    python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1], "session_id": sys.argv[2]}))' "$1" "${2:-s1}" | bash "$hook"
}
silent() {
    if [ -z "$(polish "$1")" ]; then echo "ok   silent <- ${1:0:50}"; else echo "FAIL silent <- ${1:0:50}"; fail=1; fi
}
speaks() {
    if [ -n "$(polish "$1" "$2")" ]; then echo "ok   polish <- ${1:0:50}"; else echo "FAIL polish <- ${1:0:50}"; fail=1; fi
}

silent "yes"
silent "commit and push"
silent "focus on tasks section"
silent "<task-notification>
<task-id>a1</task-id><status>completed</status><result>RESULT: GREEN, all tests passed in the suite</result>
</task-notification>"
silent "[SYSTEM NOTIFICATION - NOT USER INPUT] background shell finished with exit code zero and more words"
speaks "tasks list currently on second line, make it on last line, and collapsed by default" s2
speaks "the dashboard session view should follow the tone of the attached screenshot" s2

exit "$fail"
