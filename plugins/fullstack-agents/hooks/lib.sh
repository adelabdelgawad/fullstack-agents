#!/usr/bin/env bash
# lib.sh — shared helpers for fullstack-agents hooks.
# Sourced by hook scripts; do not execute directly.

# Execution-test the interpreter: on Windows, a Microsoft Store stub named
# python3.exe can sit on PATH and fail when actually run.
find_python() {
    local cand
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'pass' >/dev/null 2>&1; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
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
    if grep -F '"Skill"' "$transcript" 2>/dev/null | grep -qF "$skill_name"; then
        return 0
    fi
    return 1
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

# constitution_limit KEY DEFAULT
#   Read a machine-readable `key: value` line from the constitution's Limits
#   section (e.g. "max-file-lines: 600"). Echoes DEFAULT when absent/invalid.
constitution_limit() {
    local key="${1:-}" default="${2:-}" file value
    file=$(find_constitution) || { printf '%s' "$default"; return 0; }
    value=$(grep -E "^${key}:[[:space:]]*[0-9]+" "$file" 2>/dev/null \
        | head -1 | sed "s/^${key}:[[:space:]]*//" | tr -d '[:space:]')
    case "$value" in
        ''|*[!0-9]*) printf '%s' "$default" ;;
        *)           printf '%s' "$value" ;;
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
