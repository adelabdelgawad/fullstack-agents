#!/usr/bin/env bash
# Tests for scripts/fsa-skill-map and hooks/skill-gate.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
map="$here/../scripts/fsa-skill-map"
gate="$here/skill-gate"
pass=0; fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL %s\n' "$1"; }

proj="$(mktemp -d)"; trap 'rm -rf "$proj"' EXIT
mkdir -p "$proj/src/frontend" "$proj/src/backend/crates/svc/src/routes" "$proj/.codex-briefs" "$proj/.claude"
echo '{"dependencies":{"next":"15"}}' > "$proj/src/frontend/package.json"
echo '[workspace]' > "$proj/src/backend/Cargo.toml"
touch "$proj/src/backend/crates/svc/src/routes/items.rs"
mkdir -p "$proj/src/frontend/features/x" && touch "$proj/src/frontend/features/x/items-table.tsx"
git -C "$proj" init -q

skills() { printf '%s\n' "$@" | python3 "$map" --root "$proj" | tr '\n' ' '; }
expect_has() { case " $1 " in *" $2 "*) ok "$3" ;; *) bad "$3 (got: $1)" ;; esac; }
expect_not() { case " $1 " in *" $2 "*) bad "$3 (got: $1)" ;; *) ok "$3" ;; esac; }

s="$(skills src/frontend/features/x/items-table.tsx)"
expect_has "$s" data-table "a table component needs data-table"
expect_has "$s" nextjs "a table component needs nextjs"
s="$(skills 'src/frontend/app/(dashboard)/x/page.tsx')"
expect_has "$s" data-table "a dashboard page needs data-table"
s="$(skills src/frontend/lib/api/items.ts)"
expect_has "$s" fetch-architecture "the fetch layer needs fetch-architecture"
s="$(skills src/frontend/lib/api/generated/schema.d.ts)"
expect_not "$s" nextjs "generated types need nothing"
s="$(skills src/backend/crates/svc/src/routes/items.rs)"
expect_has "$s" rust-axum-api "a route needs rust-axum-api"
expect_has "$s" rust-nextjs-contract "a route in a Next.js project needs the wire contract"
expect_has "$s" rust-quality-gates "rust code needs the quality gates"
s="$(skills src/backend/migrations/1_x.sql)"
expect_has "$s" rust-sqlx "a migration in a cargo project needs rust-sqlx"
s="$(skills src/backend/crates/svc/tests/items.rs)"
expect_has "$s" rust-testing "a rust test needs rust-testing"
printf 'fn x() { sqlx::query("SELECT 1"); }\n' > "$proj/src/backend/crates/svc/src/rule_service.rs"
s="$(skills src/backend/crates/svc/src/rule_service.rs)"
expect_has "$s" rust-sqlx "rust code embedding SQL needs rust-sqlx"
s="$(skills docker-compose.prod.yml)"
expect_has "$s" docker "compose needs docker"
s="$(skills src/backend/crates/svc/src/new_module.rs)"
expect_has "$s" senior-engineer "a new source file needs senior-engineer"

transcript="$proj/t.jsonl"
skill_line() { printf '{"message":{"content":[{"type":"tool_use","id":"x","name":"Skill","input":{"skill":"fullstack-agents:%s"}}]}}\n' "$1"; }
run_gate() { # tool file content
    python3 -c 'import json,sys; print(json.dumps({"tool_name":sys.argv[1],"transcript_path":sys.argv[4],"tool_input":{"file_path":sys.argv[2],"content":sys.argv[3]}}))' "$1" "$2" "$3" "$transcript" \
        | (cd "$proj" && bash "$gate" >/dev/null 2>&1); echo $?
}
brief="GOAL: x
ALLOWED_PATHS:
src/frontend/features/x/items-table.tsx

TESTS: none"

echo '{"message":{"content":[{"type":"text","text":"invoke via the Skill tool: data-table, nextjs"}]}}' > "$transcript"
[ "$(run_gate Write "$proj/.codex-briefs/b.md" "$brief")" = 2 ] && ok "a router hint naming the skill does not count" || bad "a router hint naming the skill does not count"

skill_line nextjs >> "$transcript"
[ "$(run_gate Write "$proj/.codex-briefs/b.md" "$brief")" = 2 ] && ok "a table brief without data-table is blocked" || bad "a table brief without data-table is blocked"

skill_line data-table >> "$transcript"
[ "$(run_gate Write "$proj/.codex-briefs/b.md" "$brief")" = 0 ] && ok "a table brief passes once its skills are loaded" || bad "a table brief passes once its skills are loaded"

printf 'data-table docs/architecture/data-tables.md\n' > "$proj/.claude/fsa-skill-docs"
[ "$(run_gate Write "$proj/.codex-briefs/b.md" "$brief")" = 2 ] && ok "a brief missing its bound document is blocked" || bad "a brief missing its bound document is blocked"
[ "$(run_gate Write "$proj/.codex-briefs/b.md" "DOC: docs/architecture/data-tables.md
$brief")" = 0 ] && ok "a brief citing its bound document passes" || bad "a brief citing its bound document passes"

: > "$transcript"; skill_line nextjs >> "$transcript"
[ "$(run_gate Write "$proj/src/frontend/features/x/items-table.tsx" "x")" = 2 ] && ok "a lead edit to a table without data-table is blocked" || bad "a lead edit to a table without data-table is blocked"
r=$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Write","transcript_path":sys.argv[2],"tool_input":{"file_path":sys.argv[1],"content":"x"}}))' "$proj/src/frontend/features/x/items-table.tsx" "$transcript" | (cd "$proj" && FSA_IMPLEMENTER_RUN=1 bash "$gate" >/dev/null 2>&1); echo $?)
[ "$r" = 0 ] && ok "implementer runs are not gated" || bad "implementer runs are not gated"
r=$(python3 -c 'import json,sys; print(json.dumps({"tool_name":"Write","transcript_path":sys.argv[2],"tool_input":{"file_path":sys.argv[1],"content":"x"}}))' "$proj/src/frontend/features/x/items-table.tsx" "$transcript" | (cd "$proj" && FSA_SKIP_SKILL_GATE=1 bash "$gate" >/dev/null 2>&1); echo $?)
[ "$r" = 0 ] && ok "the off switch disables the gate" || bad "the off switch disables the gate"
[ "$(run_gate Write "$proj/notes.md" "plain notes")" = 0 ] && ok "markdown without ALLOWED_PATHS is not a brief" || bad "markdown without ALLOWED_PATHS is not a brief"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
