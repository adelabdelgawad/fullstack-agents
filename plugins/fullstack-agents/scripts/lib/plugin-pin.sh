# Sourced: the plugin identity a session pins and every dispatch compares (release manifest, or dev tree fingerprint).

fsa_pin_dir() { printf '%s' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/fullstack-agents/pins"; }

# A release directory holds RELEASE.json two levels above the plugin root (<release>/plugins/fullstack-agents).
fsa_release_root() {
  local r
  r=$(cd "$1/../.." 2>/dev/null && pwd -P) || return 1
  [ -f "$r/RELEASE.json" ] && printf '%s' "$r"
}

# Dev mode: HEAD, the index and every tracked or untracked change under the plugin root.
fsa_dev_fingerprint() {
  {
    git -C "$1" rev-parse HEAD
    git -C "$1" ls-files -s -- .
    git -C "$1" diff HEAD -- .
    git -C "$1" ls-files -o --exclude-standard -- . | while IFS= read -r f; do
      printf '%s %s\n' "$f" "$(git -C "$1" hash-object -- "$f")"
    done
  } 2>/dev/null | sha256sum | cut -d' ' -f1
}

fsa_plugin_pin() {
  local root rel version
  root=$(cd "$1" && pwd -P)
  version=$(jq -r '.version // ""' "$root/.claude-plugin/plugin.json" 2>/dev/null || true)
  if rel=$(fsa_release_root "$root"); then
    jq -n --arg root "$root" --arg v "$version" --arg rel "$rel" \
      --arg fp "$(sha256sum "$rel/RELEASE.json" | cut -d' ' -f1)" --arg sha "$(jq -r '.git_sha' "$rel/RELEASE.json")" \
      '{mode: "release", root: $root, version: $v, release_root: $rel, git_sha: $sha, fingerprint: $fp}'
  elif git -C "$root" rev-parse HEAD > /dev/null 2>&1; then
    jq -n --arg root "$root" --arg v "$version" --arg sha "$(git -C "$root" rev-parse HEAD)" \
      --arg fp "$(fsa_dev_fingerprint "$root")" '{mode: "dev", root: $root, version: $v, git_sha: $sha, fingerprint: $fp}'
  else
    jq -n --arg root "$root" --arg v "$version" '{mode: "unpinned", root: $root, version: $v, fingerprint: ""}'
  fi
}
