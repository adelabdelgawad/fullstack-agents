#!/usr/bin/env bash
# Self-check for prompt routing. Run: bash hooks/prompt-scan.test.sh
set -uo pipefail

hook="$(dirname "$0")/prompt-scan"
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

reject() {
    local prompt="$1" got
    got="$(route "$prompt")"
    if printf '%s' "$got" | grep -qF "intent: performance"; then
        echo "FAIL not performance <- ${prompt:0:60}"; fail=1
    else
        echo "ok   not performance <- ${prompt:0:60}"
    fi
}

reject "change the campaign form label"
reject "add a feature flag for exports"
reject "fix the uploading of lead files"

exit "$fail"
