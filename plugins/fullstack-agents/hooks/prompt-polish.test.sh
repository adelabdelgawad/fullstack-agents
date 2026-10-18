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
# A precise short request is already a spec; open-scope wording is not.
silent "tasks list currently on second line, make it on last line, and collapsed by default"
speaks "the dashboard session view should follow the tone of the attached screenshot" s2
# Questions, research, continuations and structured specs are never rewritten.
silent "continue"
silent "what does the edit budget gate count, and where does it read the limit from in this repository?"
silent "do github and online research for plugins like this one and compare their hook overhead in detail please"
silent "$(printf '## Goal\nImplement P5.\n## Requirements\n1. Count unique edited paths.\n## Constraints\n- No push.\n## Done when\n- tests pass')"
# A long, already precise action request (paths + acceptance) is left alone.
silent "rename json_fields in plugins/fullstack-agents/hooks/lib.sh to hook_fields and update hooks/prompt-scan and hooks/prompt-polish to match; acceptance: bash hooks/lib.test.sh passes and nothing else changes"
# A pasted report followed by a short instruction is judged by the instruction.
silent "$(printf '%s\n\nsummarise this' "$(printf 'Deploy of the backend failed and we should improve everything. %.0s' $(seq 10))")"
# A long open-scope change request, including negation and mixed intent, is refined.
speaks "investigate why the campaign list is slow on the main page and then fix whatever is causing it, but do not deploy anything and keep the change small" s3
speaks "we need to improve the whole onboarding experience so that it feels nicer for new agents and matches what the other screens do today in the product" s4

exit "$fail"
