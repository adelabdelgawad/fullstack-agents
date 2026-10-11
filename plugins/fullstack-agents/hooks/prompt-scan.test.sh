#!/usr/bin/env bash
# Self-check for prompt routing. Run: bash hooks/prompt-scan.test.sh
set -uo pipefail

hook="$(dirname "$0")/prompt-scan"
export FSA_ROUTER=regex
fail=0

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

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
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

reject "change the campaign form label"
reject "add a feature flag for exports"
reject "fix the uploading of lead files"

exit "$fail"
