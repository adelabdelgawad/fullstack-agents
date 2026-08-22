#!/usr/bin/env bash
# Self-check for transcript lookup. Run: bash hooks/lib.test.sh
set -uo pipefail

source "$(dirname "$0")/lib.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

parent="$tmp/session.jsonl"
mkdir -p "$tmp/session/subagents"
sub="$tmp/session/subagents/agent-worker-abc.jsonl"

# The match comes FIRST, followed by more "Skill" lines far larger than the 64KB
# pipe buffer. `grep -q` exits on the first match while the upstream grep is
# still writing, so it dies of SIGPIPE (141) — which `set -o pipefail` reports
# as the whole pipeline failing, i.e. "skill not found".
echo '{"message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"fullstack-agents:codebase-scanning"}}]}}' > "$parent"
big="$(head -c 100000 /dev/zero | tr '\0' 'x')"
for _ in $(seq 1 5); do
    echo "{\"message\":{\"content\":[{\"type\":\"tool_use\",\"name\":\"Skill\",\"input\":{\"skill\":\"fullstack-agents:other\",\"pad\":\"$big\"}}]}}"
done >> "$parent"
echo '{"message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"fullstack-agents:rust-sqlx"}}]}}' > "$sub"

fail=0
chk() {
    if [ "$2" = "$3" ]; then
        echo "ok   $1"
    else
        echo "FAIL $1 (want $2, got $3)"
        fail=1
    fi
}
yn() { "$@" && echo yes || echo no; }

chk "parent skill found despite pipefail + early match" \
    yes "$(yn transcript_has_skill "$parent" "codebase-scanning")"
chk "parent alone does not see a subagent-only skill" \
    no  "$(yn transcript_has_skill "$parent" "rust-sqlx")"
chk "session-wide sees a subagent-only skill" \
    yes "$(yn session_has_skill "$parent" "rust-sqlx")"
chk "session-wide still sees a parent skill" \
    yes "$(yn session_has_skill "$parent" "codebase-scanning")"
chk "unknown skill is not found" \
    no  "$(yn session_has_skill "$parent" "no-such-skill")"
chk "missing transcript is not-found, not an error" \
    no  "$(yn session_has_skill "$tmp/absent.jsonl" "codebase-scanning")"

exit $fail
