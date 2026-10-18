#!/usr/bin/env bash
# Battery for scan-gate: replays the UCM gate-agent-scan.sh cases, plus the plugin's own on/off and override cases.
set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scan-gate"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME"
unset FSA_SKIP_SCAN_GATE FSA_SKIP_WRITE_GUARD KC_CODEX_GATE_OFF CLAUDE_PROJECT_DIR
R="$T/r e p o"; mkdir -p "$R/.claude"
git -C "$R" init -q

write_conf() { printf 'scan_gate=on\n' > "$R/.claude/fsa-team.conf"; }
write_conf

run() { node -e '
process.stdout.on("error",()=>{});
const type=process.argv[1]||undefined, prompt=process.argv[2], cwd=process.argv[3];
process.stdout.write(JSON.stringify({session_id:"a",tool_name:"Agent",cwd:cwd,tool_input:{subagent_type:type,prompt:prompt}}));
' "$1" "$2" "$R" | bash "$H" >/dev/null 2>&1; echo $?; }
check() { want=$1; got=$(run "$2" "$3"); if [ "$got" = "$want" ]; then echo "ok   ($got) $4"; else echo "FAIL want=$want got=$got :: $4"; FAILED=1; fi; }
FAILED=0

GOOD='Read-only scan.
FILES:
- src/frontend/features/x/a.ts
- src/frontend/features/x/b.tsx

REPORT: file:line | symbol | owner module | value
Facts only.'
echo "--- prose briefs must BLOCK (2) ---"
check 2 fullstack-agents:bounded-extractor 'Read the owner module and report how ownership switches.' "no FILES, no REPORT"
check 2 general-purpose 'FILES:
- src/a.ts

Summarize what it does.' "FILES but no REPORT"
check 2 fullstack-agents:bounded-extractor 'FILES:
- src/a.ts

REPORT: file:line | fact
Also explain why the adapter is duplicated.' "asks why"
check 2 fullstack-agents:bounded-extractor "$GOOD
Recommend a target architecture." "asks for a recommendation"
check 2 "" 'Sweep src/frontend for pathname checks and tell me what you find.' "omitted type, prose"
check 2 Explore 'Find every importer of useOwner.' "Explore without contract"
echo "--- table-contract briefs must ALLOW (0) ---"
check 0 fullstack-agents:bounded-extractor "$GOOD" "bounded-extractor with FILES and REPORT"
check 0 general-purpose "$GOOD" "general-purpose with contract"
check 0 "" "$GOOD" "omitted type with contract"
echo "--- exempt agents ALLOW any prompt (0) ---"
check 0 fork 'Continue the audit and tell me why it failed.' "fork"
check 0 claude-code-guide 'Why does the Agent tool ignore model for fork?' "claude-code-guide"
check 0 fullstack-agents:test-runner 'Run the test suite and save the log.' "test-runner runs commands without a scan contract"
check 2 fullstack-agents:bounded-extractor 'Run the tests and summarise.' "other subagents still need the contract"
check 0 statusline-setup 'set up my status line' "statusline-setup"
check 0 fullstack-agents:web-researcher 'Research online how other Claude Code plugins size SessionStart output; why do they differ?' "web-researcher: web-only, no FILES needed"
check 2 general-purpose 'WEB ONLY: research online how other plugins size SessionStart output.' "a brief claiming web-only is not an exemption"
check 2 fullstack-agents:bounded-extractor 'Research online, then read the repo hooks and tell me what you find.' "repository work still needs the contract"
echo "--- empty prompt never blocks (0) ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{}}))' "$R" | bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) empty prompt" || { echo "FAIL want=0 got=$got :: empty prompt"; FAILED=1; }
echo "--- empty stdin never blocks (0) ---"
got=$(printf '' | bash "$H" >/dev/null 2>&1; echo $?); if [ "$got" = 0 ]; then echo "ok   (0) empty stdin"; else echo "FAIL want=0 got=$got :: empty stdin"; FAILED=1; fi

echo "--- gate off when unconfigured ---"
rm -f "$R/.claude/fsa-team.conf"
check 0 fullstack-agents:bounded-extractor 'Explain why this works.' "no scan_gate: gate does nothing"
write_conf

echo "--- invalid conf value refuses, naming the key ---"
printf 'scan_gate=maybe\n' > "$R/.claude/fsa-team.conf"
msg=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{subagent_type:"general-purpose",prompt:"explain why"}}))' "$R" | bash "$H" 2>&1 >/dev/null); got=$?
if [ "$got" = 2 ] && printf '%s' "$msg" | grep -q scan_gate; then echo "ok   (2) invalid scan_gate refuses and names the key"; else echo "FAIL want=2/scan_gate got=$got :: $msg"; FAILED=1; fi
write_conf

echo "--- FSA_SKIP_SCAN_GATE disables only this gate ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{subagent_type:"general-purpose",prompt:"explain why"}}))' "$R" | FSA_SKIP_SCAN_GATE=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) FSA_SKIP_SCAN_GATE=1 bypasses" || { echo "FAIL want=0 got=$got :: FSA_SKIP_SCAN_GATE"; FAILED=1; }
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{subagent_type:"general-purpose",prompt:"explain why"}}))' "$R" | FSA_SKIP_WRITE_GUARD=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 2 ] && echo "ok   (2) FSA_SKIP_WRITE_GUARD=1 does not bypass scan-gate" || { echo "FAIL want=2 got=$got :: FSA_SKIP_WRITE_GUARD"; FAILED=1; }

echo "--- legacy KC_CODEX_GATE_OFF disables this gate too ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{subagent_type:"fullstack-agents:bounded-extractor",prompt:"explain why"}}))' "$R" | KC_CODEX_GATE_OFF=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) KC_CODEX_GATE_OFF=1 bypasses" || { echo "FAIL want=0 got=$got :: override"; FAILED=1; }

echo "--- root falls back to CLAUDE_PROJECT_DIR when cwd is not a git repo ---"
NOGIT="$T/nogit"; mkdir -p "$NOGIT/.claude"
printf 'scan_gate=on\n' > "$NOGIT/.claude/fsa-team.conf"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{subagent_type:"general-purpose",prompt:"explain why"}}))' "$T/bare" | CLAUDE_PROJECT_DIR="$NOGIT" bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 2 ] && echo "ok   (2) CLAUDE_PROJECT_DIR is used when cwd resolves no git toplevel" || { echo "FAIL want=2 got=$got :: CLAUDE_PROJECT_DIR fallback"; FAILED=1; }

echo "--- a repository path containing a space ---"
check 2 general-purpose 'Explain why this works.' "spaced repo path"

echo
if [ "$FAILED" = 0 ]; then echo "ALL PASS"; else echo "FAILURES PRESENT"; fi
exit "$FAILED"
