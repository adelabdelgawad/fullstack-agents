#!/usr/bin/env bash
# Self-check for prompt routing. Run: bash hooks/prompt-scan.test.sh
set -uo pipefail

hook="$(cd "$(dirname "$0")" && pwd)/prompt-scan"
export FSA_ROUTER=regex
fail=0
# Lane nags only apply inside a project of that lane: run from a stub Next.js + Rust + Docker repo.
proj="$(mktemp -d)"
printf '{"dependencies":{"next":"15.0.0"}}\n' > "$proj/package.json"
printf '[package]\nname = "x"\n' > "$proj/Cargo.toml"
printf 'services: {}\n' > "$proj/docker-compose.yml"
cd "$proj" || exit 1

route() {
    python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1]}))' "$1" | bash "$hook" | head -1
}

expect() {
    local prompt="$1" want="$2" got
    got="$(route "$prompt")"
    if printf '%s' "$got" | grep -qF -- "$want"; then
        echo "ok   ${want} <- ${prompt:0:60}"
    else
        echo "FAIL ${want} <- ${prompt:0:60}"; echo "     got: ${got}"; fail=1
    fi
}

expect "when i clicked Break Reassons from the navbar, it open the page immedaitly but the page itself show skelton for arround 7 seconds then the data" "intent: performance, lane: frontend"
expect "when i clicked Break Reassons from the navbar, it open the page immedaitly but the page itself show skelton for arround 7 seconds then the data" "client-performance.md"
expect "the campaigns page takes 5s to load" "intent: performance"
expect "the dashboard freezes after an hour" "intent: performance"
expect "sqlx query is slow on the leads table" "lane: rust"
expect "the login button is broken" "intent: debug"
expect "add a nginx location for the new service" "lane: infra"
expect "why does the sidebar show the wrong group" "lane: frontend"
expect "why does the sidebar show the wrong group" "load these NOW, before the root cause"
expect "add a create button to the campaigns data table" "data-freshness.md"
expect "the EventSource stays closed after the realtime service restarts" "lane: frontend"
expect "the EventSource stays closed after the realtime service restarts" "live-updates.md"
expect "facet clicks wait before the list reloads" "client-performance.md"

reject() {
    local prompt="$1" got
    got="$(route "$prompt")"
    if printf '%s' "$got" | grep -qF "intent: performance"; then
        echo "FAIL not performance <- ${prompt:0:60}"; fail=1
    else
        echo "ok   not performance <- ${prompt:0:60}"
    fi
}

route_all() {
    python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1], "transcript_path": sys.argv[2]}))' "$1" "$2" | bash "$hook"
}

check() {
    local name="$1" cond="$2"
    if [ "$cond" = 1 ]; then echo "ok   ${name}"; else echo "FAIL ${name}"; fail=1; fi
}

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp" "$proj"' EXIT
printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"no skills yet"}]}}' > "$tmp/empty.jsonl"
printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"fullstack-agents:nextjs"}}]}}' > "$tmp/loaded.jsonl"
fe="the conversation page shows the list after the page paints"

out="$(route_all "$fe" "$tmp/empty.jsonl")"
check "lane skill missing -> NOT LOADED line" "$(printf '%s' "$out" | grep -qF 'LANE SKILL NOT LOADED THIS SESSION: nextjs' && echo 1 || echo 0)"
out="$(route_all "$fe" "$tmp/loaded.jsonl")"
check "lane skill loaded -> no NOT LOADED line" "$(printf '%s' "$out" | grep -qF 'NOT LOADED' && echo 0 || echo 1)"
check "lane skill loaded -> no repeated 'load these NOW'" "$(printf '%s' "$out" | grep -qF 'load these NOW' && echo 0 || echo 1)"
out="$(route_all "<system-reminder>
[SYSTEM NOTIFICATION - NOT USER INPUT]
Monitor event: build progress" "$tmp/empty.jsonl")"
check "automated notification -> silent" "$([ -z "$out" ] && echo 1 || echo 0)"
out="$(route_all "<task-notification>
<task-id>a1</task-id><status>completed</status>
</task-notification>" "$tmp/empty.jsonl")"
check "task notification -> silent" "$([ -z "$out" ] && echo 1 || echo 0)"
plain="$(mktemp -d)"
out="$(cd "$plain" && route_all "$fe" "$tmp/empty.jsonl")"
rm -rf "$plain"
check "no Next.js project -> no NOT LOADED line" "$(printf '%s' "$out" | grep -qF 'NOT LOADED' && echo 0 || echo 1)"
check "no Next.js project -> no stack doctrine" "$(printf '%s' "$out" | grep -qF 'STACK TOPIC DETECTED' && echo 0 || echo 1)"
out="$(cd "$tmp" && route_all "the terminal scroller is very slow on vpn" "$tmp/empty.jsonl")"
check "performance outside Next.js -> no nextjs skills" "$(printf '%s' "$out" | grep -qF 'nextjs' && echo 0 || echo 1)"
check "no Next.js project -> no 'load these NOW'" "$(printf '%s' "$out" | grep -qF 'load these NOW' && echo 0 || echo 1)"

# Router selection: copy the plugin with a stub Haiku classifier that announces itself.
stub="$tmp/plugin"
mkdir -p "$stub/scripts"
cp -r "$(dirname "$hook")" "$stub/hooks"
cp -r "$(dirname "$hook")/../scripts/lib" "$stub/scripts/lib"  # route.py classifies before any Haiku call
printf 'print("[stub] haiku routed")\nprint("")\n' > "$stub/scripts/fsa-classify"
routed_by() {  # router prompt
    python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1]}))' "$2" | FSA_ROUTER="$1" bash "$stub/hooks/prompt-scan" | head -1
}
haiku_used() { routed_by "$1" "$2" | grep -qF '[stub] haiku' && echo 1 || echo 0; }
check "auto: regex hit skips Haiku" "$([ "$(haiku_used auto 'the login button is broken on the settings page')" = 0 ] && echo 1 || echo 0)"
check "auto: unclassified long prompt asks Haiku" "$(haiku_used auto 'is this dashboard secured enough to publish on my public address')"
check "auto: unclassified short prompt stays silent" "$([ -z "$(routed_by auto 'commit and push')" ] && echo 1 || echo 0)"
check "haiku: always asks Haiku" "$(haiku_used haiku 'the login button is broken on the settings page')"
check "regex: never asks Haiku" "$([ -z "$(routed_by regex 'is this dashboard secured enough to publish on my public address')" ] && echo 1 || echo 0)"
check "default router is auto" "$(python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1]}))' 'is this dashboard secured enough to publish on my public address' | env -u FSA_ROUTER bash "$stub/hooks/prompt-scan" | grep -qF '[stub] haiku' && echo 1 || echo 0)"

# P3: clause routing. Questions and research route without task-flow; isolated words never decide intent.
expect "what does the edit budget gate count?" "intent: question"
expect "do github and online research for such plugin like fullstack-agent, compare it against it, find the bottle neck on the fsa, and wrong created setup" "intent: research"
expect "do github and online research for such plugin like fullstack-agent, compare it against it" "web-researcher"
expect "fix the flaky dashboard test; do not deploy and do not push" "intent: debug"
expect "fix the flaky dashboard test; do not deploy and do not push" "Prohibited by the prompt (constraints, not intents): deploy"
expect "deploy the frontend" "intent: deploy"
expect "investigate why the users page is slow, then fix the cause" "intent: investigate+implement"
expect "$(printf '## Goal\nImplement the complete overhead-reduction plan.\n## Context\n- SQLx and Axum crates.\n## Constraints\n- No deployment, release or push.\n## Done when\n- Commits ready.')" "intent: implement, lane: any"
expect "$(printf '%s\n\nsummarise this' "$(printf 'The deploy failed in the rust worker and nginx crashed. %.0s' $(seq 12))")" "intent: question, lane: any"
expect "$(printf 'Report: %s\n\nfix the second item' "$(printf 'deploy step broke. %.0s' $(seq 30))")" "intent: debug"
none_of() {  # prompt unwanted
    local got; got="$(route "$1")"
    if printf '%s' "$got" | grep -qF -- "$2"; then echo "FAIL not '$2' <- ${1:0:60}"; echo "     got: $got"; fail=1; else echo "ok   not '$2' <- ${1:0:60}"; fi
}
none_of "do not deploy" "intent: deploy"
none_of "the setup was created wrong, find out why" "intent: implement"
none_of "$(printf '## Goal\nDetermine whether data improved transcription.\n## Constraints\n- No training, annotation changes or deployment.')" "intent: deploy"
none_of "$(printf '## Goal\nCompare two runs.\n## Context\nThe SQLx and Axum crates are unrelated.')" "lane: rust"
check "question skips Haiku in auto mode" "$([ "$(haiku_used auto 'what does the edit budget gate count in this repository?')" = 0 ] && echo 1 || echo 0)"
check "research skips Haiku in auto mode" "$([ "$(haiku_used auto 'research online how other plugins size their hook output')" = 0 ] && echo 1 || echo 0)"

reject "change the campaign form label"
reject "add a feature flag for exports"
reject "fix the uploading of lead files"

exit "$fail"
