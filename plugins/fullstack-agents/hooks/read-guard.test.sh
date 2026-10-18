#!/usr/bin/env bash
# Battery for read-guard: replays the UCM guard-source-reads.sh cases, plus the plugin's own on/off and
# override cases. Nothing is skipped: this hook has no run-ownership concept to port.
set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/read-guard"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME"
unset FSA_SKIP_READ_GUARD KC_CODEX_GATE_OFF KC_READ_RANGE_MAX CLAUDE_PROJECT_DIR
R="$T/r e p o"; mkdir -p "$R/.claude"
git -C "$R" init -q

write_conf() { printf 'read_range_max=%s\ngated_extensions=rs ts tsx\n' "${1:-200}" > "$R/.claude/fsa-team.conf"; }
write_conf

run() { node -e '
process.stdout.on("error",()=>{});
const cmd=process.argv[1], desc=process.argv[2]||"d", cwd=process.argv[3];
process.stdout.write(JSON.stringify({session_id:"a",tool_name:"Bash",cwd:cwd,tool_input:{command:cmd,description:desc}}));
' "$1" "${2:-d}" "$R" | bash "$H" >/dev/null 2>&1; echo $?; }
check() { want=$1; got=$(run "$2" "${3:-d}"); if [ "$got" = "$want" ]; then echo "ok   ($got) $2"; else echo "FAIL want=$want got=$got :: $2"; FAILED=1; fi; }
FAILED=0

echo "--- unranged dumps of source must BLOCK (2) ---"
check 2 'cat src/a.ts'
check 2 'cat -n src/deep/x.tsx'
check 2 'nl src/a.rs'
check 2 'less src/a.rs'
check 2 'cat src/a.ts | grep foo'
check 2 'sed -n 1,400p src/a.rs'
check 2 'sed -n /foo/,/bar/p src/a.ts'
check 2 'sed -n 10,$p src/a.ts'
check 2 'sed s/a/b/ src/a.ts'
check 2 'head -n 500 src/a.ts'
check 2 'head -500 src/a.ts'
check 2 'tail -n 300 x.tsx'
check 2 'W=/repo; cat -n "$W/src/a.tsx"'
check 2 'for f in a.tsx b.tsx; do echo ==; cat -n "$f"; done'
check 2 'sed -n 1,40p src/a.rs && sed -n 1,400p src/a.rs'
echo "--- ranged reads must ALLOW (0) ---"
check 0 'sed -n 1,40p src/a.rs'
check 0 'sed -n 120,+80p x.ts'
check 0 'sed -n 12p a.ts'
check 0 'sed -n /foo/= src/a.ts'
check 0 'sed -n 1,40p src/a.rs && sed -n 400,440p src/a.rs'
check 0 'head -n 50 a.ts'
check 0 'head a.ts'
check 0 'tail -n 20 a.ts'
check 0 'tail -20 a.ts'
echo "--- filters and non-source must ALLOW (0) ---"
check 0 'grep -n foo src/a.ts'
check 0 'grep -rn foo src/ | head -50'
check 0 'awk /foo/ src/a.ts'
check 0 'wc -l src/a.ts'
check 0 'cat README.md'
check 0 'cat -n scripts/x.sh'
check 0 'cat package.json | jq .name'
check 0 'head -n 500 docs/a.md'
check 0 'git show HEAD:src/a.ts'
check 0 'git diff -- src/a.ts'
check 0 'cargo build 2>&1 | tail -20'
check 0 'tail -f /var/log/x.log'
check 0 'sed -i s/a/b/ src/x.rs'
check 0 'for f in a.md b.md; do cat "$f"; done'
check 0 'W=/repo; cat "$W/src/backend/migrations/x.sql"; git diff -- src/a.rs'
check 2 'W=/repo; cat "$W/src/a.tsx"; git diff -- src/b.rs'
check 0 'OUT=/tmp/o.txt; sed -n "/^touched/,/^allowed/p" "$OUT" | grep src/a.tsx'
check 0 'L=/tmp/run.log; tail -c 700 "$L"; git diff -- src/a.rs'
echo "--- limit is configurable (via conf) ---"
write_conf 50
check 2 'sed -n 1,80p src/a.rs'
write_conf 500
check 0 'sed -n 1,400p src/a.rs'
write_conf 200
echo "--- description must NOT trigger ---"
check 0 'ls -la' 'Dump cat src/main.rs style'
echo "--- heredoc body must NOT trigger ---"
check 0 'cat > /tmp/doc.md <<EOF
cat src/a.ts
EOF'

echo "--- gate off when unconfigured ---"
rm -f "$R/.claude/fsa-team.conf"
check 0 'cat src/a.ts' "no read_range_max: gate does nothing"
write_conf

echo "--- invalid conf value refuses, naming the key ---"
printf 'read_range_max=not-a-number\n' > "$R/.claude/fsa-team.conf"
msg=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"cat src/a.ts"}}))' "$R" | bash "$H" 2>&1 >/dev/null); got=$?
if [ "$got" = 2 ] && printf '%s' "$msg" | grep -q read_range_max; then echo "ok   (2) invalid read_range_max refuses and names the key"; else echo "FAIL want=2/read_range_max got=$got :: $msg"; FAILED=1; fi
write_conf

echo "--- FSA_SKIP_READ_GUARD disables only this gate ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"cat src/a.ts"}}))' "$R" | FSA_SKIP_READ_GUARD=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) FSA_SKIP_READ_GUARD=1 bypasses" || { echo "FAIL want=0 got=$got :: FSA_SKIP_READ_GUARD"; FAILED=1; }

echo "--- legacy KC_CODEX_GATE_OFF disables this gate too ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"cat src/a.ts"}}))' "$R" | KC_CODEX_GATE_OFF=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) KC_CODEX_GATE_OFF=1 bypasses" || { echo "FAIL want=0 got=$got :: override"; FAILED=1; }

echo "--- legacy KC_READ_RANGE_MAX overrides the conf value ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"sed -n 1,80p src/a.rs"}}))' "$R" | KC_READ_RANGE_MAX=50 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 2 ] && echo "ok   (2) KC_READ_RANGE_MAX=50 overrides read_range_max=200" || { echo "FAIL want=2 got=$got :: KC_READ_RANGE_MAX"; FAILED=1; }

echo "--- root falls back to CLAUDE_PROJECT_DIR when cwd is not a git repo ---"
NOGIT="$T/nogit"; mkdir -p "$NOGIT/.claude"
printf 'read_range_max=200\ngated_extensions=rs ts tsx\n' > "$NOGIT/.claude/fsa-team.conf"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"cat src/a.ts"}}))' "$T/bare" | CLAUDE_PROJECT_DIR="$NOGIT" bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 2 ] && echo "ok   (2) CLAUDE_PROJECT_DIR is used when cwd resolves no git toplevel" || { echo "FAIL want=2 got=$got :: CLAUDE_PROJECT_DIR fallback"; FAILED=1; }

echo "--- a repository path containing a space ---"
check 2 'cat src/a.ts'

echo
if [ "$FAILED" = 0 ]; then echo "ALL PASS"; else echo "FAILURES PRESENT"; fi
exit "$FAILED"
