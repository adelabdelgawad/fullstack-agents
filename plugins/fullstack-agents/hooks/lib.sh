#!/usr/bin/env bash
# lib.sh — shared helpers for fullstack-agents hooks.
# Sourced by hook scripts; do not execute directly.

# Execution-test the interpreter: on Windows, a Microsoft Store stub named
# python3.exe can sit on PATH and fail when actually run.
# Only Windows shells need the execution test; elsewhere `command -v` suffices
# and avoids starting an interpreter on every hook call.
find_python() {
    local cand
    for cand in python3 python; do
        command -v "$cand" >/dev/null 2>&1 || continue
        case "${OSTYPE:-}" in
            msys*|cygwin*|win32*) "$cand" -c 'pass' >/dev/null 2>&1 || continue ;;
        esac
        printf '%s' "$cand"
        return 0
    done
    return 1
}

# json_fields JSON_STRING FIELD_PATH...
#   Read several dotted field paths with ONE interpreter start. Sets the array
#   JSON_FIELDS, one element per path ("" when absent; booleans as true/false).
json_fields() {
    local json_str="${1:-}" py v f
    shift
    JSON_FIELDS=()
    py=$(find_python || true)
    if [ -n "$py" ] && [ -n "$json_str" ]; then
        while IFS= read -r -d '' v; do JSON_FIELDS+=("$v"); done < <(printf '%s' "$json_str" | "$py" -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    data = {}
for field in sys.argv[1:]:
    obj = data
    for key in field.split("."):
        obj = obj.get(key) if isinstance(obj, dict) else None
    if obj is None:
        out = ""
    elif isinstance(obj, bool):
        out = "true" if obj else "false"
    elif isinstance(obj, str):
        out = obj
    elif isinstance(obj, (int, float)):
        out = str(obj)
    else:
        out = json.dumps(obj)
    sys.stdout.write(out.replace("\0", "") + "\0")' "$@" 2>/dev/null)
    fi
    if [ "${#JSON_FIELDS[@]}" -ne "$#" ]; then
        JSON_FIELDS=()
        for f in "$@"; do JSON_FIELDS+=("$(json_get_field "$f" "$json_str")"); done
    fi
}

# json_get_field FIELD_PATH JSON_STRING
#   Extract a dotted field path from a JSON string. Outputs the value or "".
json_get_field() {
    local field="${1:-}" json_str="${2:-}"
    [ -n "$json_str" ] || { printf ''; return 0; }

    local py
    py=$(find_python || true)
    if [ -n "$py" ]; then
        printf '%s' "$json_str" | "$py" -c '
import json, sys
field = sys.argv[1]
try:
    obj = json.load(sys.stdin)
    for key in field.split("."):
        obj = obj[key] if isinstance(obj, dict) and key in obj else None
        if obj is None:
            break
    print("" if obj is None else obj, end="")
except Exception:
    pass' "$field"
    elif command -v jq >/dev/null 2>&1; then
        printf '%s' "$json_str" | jq -r ".${field} // \"\"" 2>/dev/null || printf ''
    else
        # last-resort: top-level string field only; unescape Windows backslashes
        local leaf="${field##*.}"
        printf '%s' "$json_str" \
            | sed -n "s/.*\"${leaf}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" \
            | sed 's/\\\\/\\/g'
    fi
}

# transcript_has_skill TRANSCRIPT_PATH SKILL_NAME
#   Search the JSONL transcript for Skill tool calls naming SKILL_NAME.
#   Skill invocations appear as "name":"Skill" with "skill":"plugin:name" on
#   the same JSONL line. Returns 0 if found.
transcript_has_skill() {
    local transcript="${1:-}" skill_name="${2:-}"
    [ -n "$transcript" ] && [ -f "$transcript" ] || return 1
    # Single process, no pipeline: `grep -q` closing the pipe early makes the
    # upstream grep exit 141, which `set -o pipefail` reports as not-found.
    # Only a real Skill tool call or slash command counts; a hint that merely names the skill does not.
    local bare="${skill_name#fullstack-agents:}"
    awk -v a="\"name\":\"Skill\",\"input\":{\"skill\":\"fullstack-agents:${bare}\"" \
        -v b="\"name\":\"Skill\",\"input\":{\"skill\":\"${bare}\"" \
        -v c="<command-name>/fullstack-agents:${bare}</command-name>" '
        index($0, a) || index($0, b) || index($0, c) { found = 1; exit }
        END { exit !found }
    ' "$transcript" 2>/dev/null
}

session_loaded_skill() { session_has_skill "$@"; }

# session_missing_skills TRANSCRIPT_PATH SKILL_NAME...
#   PreToolUse carries no agent identity, so a subagent's edit arrives with the
#   parent transcript path; its own Skill calls live in <session-dir>/subagents/.
#   Prints each named skill (as given) that neither the parent transcript nor any
#   subagent transcript of that session loaded. One awk pass over all files.
session_missing_skills() {
    local transcript="${1:-}" sub
    shift
    [ "$#" -gt 0 ] || return 0
    local files=()
    [ -n "$transcript" ] && [ -f "$transcript" ] && files+=("$transcript")
    if [ -n "$transcript" ]; then
        for sub in "${transcript%.jsonl}"/subagents/*.jsonl; do
            [ -f "$sub" ] && files+=("$sub")
        done
    fi
    if [ "${#files[@]}" -eq 0 ]; then
        printf '%s\n' "$@"
        return 0
    fi
    awk -v list="$*" '
        BEGIN {
            n = split(list, want, " "); left = n
            for (i = 1; i <= n; i++) { b = want[i]; sub(/^fullstack-agents:/, "", b); bare[i] = b }
        }
        index($0, "\"name\":\"Skill\"") || index($0, "<command-name>/fullstack-agents:") {
            for (i = 1; i <= n; i++) {
                if (hit[i]) continue
                b = bare[i]
                if (index($0, "\"name\":\"Skill\",\"input\":{\"skill\":\"fullstack-agents:" b "\"") \
                    || index($0, "\"name\":\"Skill\",\"input\":{\"skill\":\"" b "\"") \
                    || index($0, "<command-name>/fullstack-agents:" b "</command-name>")) { hit[i] = 1; left-- }
            }
            if (!left) exit
        }
        END { for (i = 1; i <= n; i++) if (!hit[i]) print want[i] }
    ' "${files[@]}" 2>/dev/null
}

# session_has_skill TRANSCRIPT_PATH SKILL_NAME
#   0 when the session (parent or any subagent) loaded SKILL_NAME.
session_has_skill() {
    [ -n "${2:-}" ] || return 1
    [ -z "$(session_missing_skills "${1:-}" "$2")" ]
}

# find_constitution
#   Echo the path of the project constitution, searching the standard
#   locations (spec-kit first). Returns 1 when none exists.
find_constitution() {
    local cand
    for cand in ".specify/memory/constitution.md" "constitution.md" \
                "CONSTITUTION.md" ".claude/constitution.md"; do
        if [ -f "$cand" ]; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
}

# conf_load ROOT KEY...
#   Read several .claude/fsa-team.conf keys with ONE interpreter start (scripts/lib/team_conf.py get-many).
#   Sets CONF[<key>] to each typed value ("" when absent). Returns 3 and sets CONF_BAD=<key> on the first
#   invalid value. Never cached: the file is parsed on every call, so edits apply immediately.
conf_load() {
    local root=$1 i=0 status value key
    shift
    declare -gA CONF=()
    CONF_BAD=""
    local -a out=()
    mapfile -d '' -t out < <(python3 -I "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/team_conf.py" get-many "$root" "$@" 2>/dev/null)
    # A parser crash (e.g. a non-UTF-8 conf) must not read as "every key absent" and switch the gates off.
    if [ "${#out[@]}" -ne $(( 2 * $# )) ] && [ -f "$root/.claude/fsa-team.conf" ]; then
        CONF_BAD="${1} (fsa-team.conf could not be parsed)"
        return 3
    fi
    for key in "$@"; do
        status="${out[$i]:-ok}"; value="${out[$((i + 1))]:-}"; i=$((i + 2))
        if [ "$status" = invalid ]; then CONF_BAD=$key; return 3; fi
        CONF[$key]=$value
    done
    return 0
}

# state_dir
#   Echo the per-plugin state directory (for session-scoped flags) and ensure
#   it exists. Prunes stale flags older than a day.
state_dir() {
    local dir="${TMPDIR:-/tmp}/fullstack-agents-state"
    mkdir -p "$dir" 2>/dev/null
    find "$dir" -type f -mtime +1 -delete 2>/dev/null
    printf '%s' "$dir"
}

# project_has_lane <frontend|rust|python|infra>
#   Returns 0 when the cwd holds a project of that lane, so lane nags stay
#   silent in repositories the lane does not apply to.
project_has_lane() {
    case "$1" in
        frontend) grep -qs '"next"' package.json src/frontend/package.json \
                  || [ -n "$(find . -maxdepth 3 -name package.json -not -path '*/node_modules/*' -exec grep -l '"next"' {} + 2>/dev/null | head -1)" ] ;;
        rust)     [ -n "$(find . -maxdepth 3 -name Cargo.toml -not -path '*/target/*' 2>/dev/null | head -1)" ] ;;
        python)   grep -qsiE 'fastapi|sqlalchemy|celery' pyproject.toml requirements.txt src/backend/pyproject.toml ;;
        infra)    [ -n "$(find . -maxdepth 2 \( -name 'docker-compose*.y*ml' -o -name 'compose*.y*ml' -o -name Dockerfile \) 2>/dev/null | head -1)" ] ;;
        *)        return 1 ;;
    esac
}

# is_fullstack_project
#   Returns 0 when the cwd looks like a project this plugin governs
#   (FastAPI, Rust workspace, or Next.js).
is_fullstack_project() {
    if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ] \
        || [ -f "src/backend/pyproject.toml" ]; then
        return 0
    fi
    if [ -f "Cargo.toml" ] || [ -n "$(find . -maxdepth 2 -name Cargo.toml -not -path './target/*' 2>/dev/null | head -1)" ]; then
        return 0
    fi
    if { [ -f "package.json" ] && grep -q '"next"' package.json 2>/dev/null; } \
        || { [ -f "src/frontend/package.json" ] && grep -q '"next"' src/frontend/package.json 2>/dev/null; }; then
        return 0
    fi
    return 1
}
