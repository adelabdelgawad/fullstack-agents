#!/usr/bin/env bash
# Tests for scripts/fsa-classify with a stubbed model: routing output, fallback, and the reply wait mark.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CL="${HERE}/../scripts/fsa-classify"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CLAUDE_CONFIG_DIR="$TMP/cfg" FSA_TEAM_BOARD="$TMP/board.json"
PASS=0; FAIL=0
ok() { if [ "$1" = "true" ]; then PASS=$((PASS+1)); echo "ok   $2"; else FAIL=$((FAIL+1)); echo "FAIL $2 ($3)"; fi; }
stub() { printf '#!/usr/bin/env bash\ncat >/dev/null\necho %q\n' "$1" > "$TMP/stub"; chmod +x "$TMP/stub"; export FSA_CLASSIFIER_CMD="$TMP/stub"; }

stub '{"is_error":false,"structured_output":{"intent":"debug","lanes":["rust"],"skills":["debug","rust-correctness"],"worker":"none","confidence":0.9,"reason":"a Rust bug"}}'
out=$(echo '{"prompt":"the call ends twice"}' | python3 "$CL" prompt); rc=$?
ok "$([ $rc -eq 0 ] && echo "$out" | head -1 | grep -q 'intent debug, lanes rust -> invoke via the Skill tool (fullstack-agents:\*): debug, rust-correctness' && echo true)" "a confident route prints the skills" "$out"
ok "$([ "$(echo "$out" | sed -n 2p)" = rust ] && echo true)" "the second line names the primary lane" "$out"
ok "$(grep -q '"mode": "prompt"' "$TMP/cfg/fullstack-agents/classifier.jsonl" && echo true)" "the decision is logged" ""

stub '{"is_error":false,"structured_output":{"intent":"debug","lanes":["rust"],"skills":["not-a-skill"],"worker":"none","confidence":0.9,"reason":"x"}}'
out=$(echo '{"prompt":"x"}' | python3 "$CL" prompt)
ok "$(echo "$out" | head -1 | grep -q 'no skill needed' && echo true)" "an unknown skill name is dropped" "$out"

stub '{"is_error":false,"structured_output":{"intent":"debug","lanes":[],"skills":["debug"],"worker":"none","confidence":0.3,"reason":"unsure"}}'
echo '{"prompt":"x"}' | python3 "$CL" prompt >/dev/null; ok "$([ $? -eq 1 ] && echo true)" "low confidence falls back" ""
stub 'not json'
echo '{"prompt":"x"}' | python3 "$CL" prompt >/dev/null; ok "$([ $? -eq 1 ] && echo true)" "a model failure falls back" ""
FSA_CLASSIFIER_RUN=1 python3 "$CL" prompt <<< '{"prompt":"x"}' >/dev/null; ok "$([ $? -eq 2 ] && echo true)" "it refuses to run inside its own model call" ""

printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"Reply approved and I start stage 1."}]}}' > "$TMP/t.jsonl"
stub '{"is_error":false,"structured_output":{"awaiting":"approval","need":"approve the staged plan","confidence":0.9}}'
echo "{\"session_id\":\"S1\",\"transcript_path\":\"$TMP/t.jsonl\"}" | python3 "$CL" reply
need=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["waits"]["S1"]["need"])' "$FSA_TEAM_BOARD" 2>/dev/null)
ok "$([ "$need" = "approval: approve the staged plan" ] && echo true)" "a waiting reply marks the session" "$need"
stub '{"is_error":false,"structured_output":{"awaiting":"none","need":"","confidence":0.95}}'
echo "{\"session_id\":\"S2\",\"transcript_path\":\"$TMP/t.jsonl\"}" | python3 "$CL" reply
has=$(python3 -c 'import json,sys; print("S2" in json.load(open(sys.argv[1]))["waits"])' "$FSA_TEAM_BOARD")
ok "$([ "$has" = False ] && echo true)" "a finished report marks nothing" "$has"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
