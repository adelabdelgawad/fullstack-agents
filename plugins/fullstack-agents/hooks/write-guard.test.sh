#!/usr/bin/env bash
# Battery for write-guard: replays the UCM guard-source-writes.sh cases, plus the plugin's own on/off and
# override cases.
set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/write-guard"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME"
unset FSA_SKIP_WRITE_GUARD FSA_SKIP_SCAN_GATE KC_CODEX_GATE_OFF CLAUDE_PROJECT_DIR
R="$T/r e p o"; mkdir -p "$R/.claude"
git -C "$R" init -q

write_conf() { printf 'gated_extensions=rs ts tsx\n' > "$R/.claude/fsa-team.conf"; }
write_conf

run() { node -e '
process.stdout.on("error",()=>{});
const cmd=process.argv[1], desc=process.argv[2]||"d", cwd=process.argv[3];
process.stdout.write(JSON.stringify({session_id:"a",tool_name:"Bash",cwd:cwd,tool_input:{command:cmd,description:desc}}));
' "$1" "${2:-d}" "$R" | bash "$H" >/dev/null 2>&1; echo $?; }
check() { want=$1; got=$(run "$2" "${3:-d}"); if [ "$got" = "$want" ]; then echo "ok   ($got) $2"; else echo "FAIL want=$want got=$got :: $2"; FAILED=1; fi; }
FAILED=0

echo "--- must BLOCK (2) ---"
check 2 'printf x > src/a.rs'
check 2 'S=/tmp/p; printf "fn main(){}" > "$S/probe.rs" && echo done'
check 2 "cat > 'foo.tsx' <<EOF"
check 2 'sed -i s/a/b/ src/x.rs'
check 2 'echo x | tee out.ts'
check 2 'echo x >> lib/y.ts'
check 2 'cat >"src/deep/mod.rs" <<E'
echo "--- must ALLOW (0) ---"
check 0 'cargo fmt'
check 0 'cargo clippy --workspace -- -D warnings'
check 0 'cargo build 2> err.log'
check 0 'grep -rn foo src/main.rs > /tmp/out.txt'
check 0 'sed -n 1,40p src/a.rs'
check 0 'cat src/main.rs'
check 0 'npx tsc --noEmit'
check 0 'pnpm build 2>&1 | tee /tmp/build.log'
check 0 'cargo test --workspace 2>&1 | tail -20'
check 0 'git diff --cached'
check 0 'docker compose up -d'
check 0 'git log --oneline -6'
echo "--- description must NOT trigger ---"
check 0 'cargo build' 'Build and dump output > notes.rs style'
check 0 'ls -la' 'List files in src/main.rs dir'
echo "--- heredoc body must NOT trigger ---"
check 0 'cat > /tmp/doc.md <<EOF
printf x > src/a.rs
EOF'

echo "--- gate off when unconfigured ---"
rm -f "$R/.claude/fsa-team.conf"
check 0 'printf x > src/a.rs' "no gated_extensions: gate does nothing"
write_conf

echo "--- FSA_SKIP_WRITE_GUARD disables only this gate ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"printf x > src/a.rs"}}))' "$R" | FSA_SKIP_WRITE_GUARD=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) FSA_SKIP_WRITE_GUARD=1 bypasses" || { echo "FAIL want=0 got=$got :: FSA_SKIP_WRITE_GUARD"; FAILED=1; }
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"printf x > src/a.rs"}}))' "$R" | FSA_SKIP_SCAN_GATE=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 2 ] && echo "ok   (2) FSA_SKIP_SCAN_GATE=1 does not bypass write-guard" || { echo "FAIL want=2 got=$got :: FSA_SKIP_SCAN_GATE"; FAILED=1; }

echo "--- legacy KC_CODEX_GATE_OFF disables this gate too ---"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"printf x > src/a.rs"}}))' "$R" | KC_CODEX_GATE_OFF=1 bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 0 ] && echo "ok   (0) KC_CODEX_GATE_OFF=1 bypasses" || { echo "FAIL want=0 got=$got :: override"; FAILED=1; }

echo "--- root falls back to CLAUDE_PROJECT_DIR when cwd is not a git repo ---"
NOGIT="$T/nogit"; mkdir -p "$NOGIT/.claude"
printf 'gated_extensions=rs ts tsx\n' > "$NOGIT/.claude/fsa-team.conf"
got=$(node -e 'process.stdout.on("error",()=>{});process.stdout.write(JSON.stringify({cwd:process.argv[1],tool_input:{command:"printf x > src/a.rs"}}))' "$T/bare" | CLAUDE_PROJECT_DIR="$NOGIT" bash "$H" >/dev/null 2>&1; echo $?)
[ "$got" = 2 ] && echo "ok   (2) CLAUDE_PROJECT_DIR is used when cwd resolves no git toplevel" || { echo "FAIL want=2 got=$got :: CLAUDE_PROJECT_DIR fallback"; FAILED=1; }

echo "--- a repository path containing a space ---"
check 2 'printf x > src/a.rs'

echo
if [ "$FAILED" = 0 ]; then echo "ALL PASS"; else echo "FAILURES PRESENT"; fi
exit "$FAILED"
