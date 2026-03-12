#!/usr/bin/env bash
set -euo pipefail

# fullstack-agents plugin installer/updater
# Usage:
#   ./install.sh [project-path]
#   ./install.sh                           # installs to current directory
#   ./install.sh /path/to/my-project       # installs to specific project
#   ./install.sh --uninstall [project-path] # removes plugin from project

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SOURCE="${SCRIPT_DIR}/plugins/fullstack-agents"
PLUGIN_NAME="fullstack-agents"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

get_version() {
  python3 -c "import json; print(json.load(open('${PLUGIN_SOURCE}/.claude-plugin/plugin.json'))['version'])" 2>/dev/null \
    || echo "unknown"
}

get_installed_version() {
  local target="$1"
  local manifest="${target}/.claude/.claude-plugins/${PLUGIN_NAME}/.claude-plugin/plugin.json"
  if [[ -f "$manifest" ]]; then
    python3 -c "import json; print(json.load(open('${manifest}'))['version'])" 2>/dev/null \
      || echo "none"
  else
    echo "none"
  fi
}

install_plugin() {
  local target="$1"
  local version
  version="$(get_version)"
  local installed_version
  installed_version="$(get_installed_version "$target")"

  info "Plugin: ${PLUGIN_NAME} v${version}"
  info "Target: ${target}"

  if [[ "$installed_version" != "none" ]]; then
    if [[ "$installed_version" == "$version" ]]; then
      warn "Same version (v${installed_version}) already installed. Forcing update..."
    else
      info "Upgrading v${installed_version} → v${version}"
    fi
  else
    info "Fresh install"
  fi

  # Verify source exists
  if [[ ! -d "$PLUGIN_SOURCE" ]]; then
    error "Plugin source not found: ${PLUGIN_SOURCE}"
    exit 1
  fi

  # Create target directories
  local plugin_dest="${target}/.claude/.claude-plugins/${PLUGIN_NAME}"
  mkdir -p "${plugin_dest}"

  # Sync plugin files (excluding .git, __pycache__, etc.)
  rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    "${PLUGIN_SOURCE}/" "${plugin_dest}/"

  ok "Plugin files synced to ${plugin_dest}"

  # Configure settings.local.json
  local settings_file="${target}/.claude/settings.local.json"
  if [[ -f "$settings_file" ]]; then
    # Check if plugin is already configured
    if python3 -c "
import json, sys
with open('${settings_file}') as f:
    s = json.load(f)
if '${PLUGIN_NAME}@local-plugins' in s.get('enabledPlugins', {}):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
      ok "Plugin already enabled in settings"
    else
      # Add plugin to existing settings
      python3 -c "
import json
with open('${settings_file}') as f:
    s = json.load(f)
s.setdefault('enabledPlugins', {})['${PLUGIN_NAME}@local-plugins'] = True
s.setdefault('extraKnownMarketplaces', {})['local-plugins'] = {
    'source': {'source': 'directory', 'path': '.claude/.claude-plugins'}
}
with open('${settings_file}', 'w') as f:
    json.dump(s, f, indent=2)
    f.write('\n')
"
      ok "Plugin enabled in settings.local.json"
    fi
  else
    # Create settings.local.json
    mkdir -p "${target}/.claude"
    cat > "$settings_file" << 'SETTINGS'
{
  "enabledPlugins": {
    "fullstack-agents@local-plugins": true
  },
  "extraKnownMarketplaces": {
    "local-plugins": {
      "source": {
        "source": "directory",
        "path": ".claude/.claude-plugins"
      }
    }
  }
}
SETTINGS
    ok "Created settings.local.json with plugin enabled"
  fi

  echo ""
  ok "Installed ${PLUGIN_NAME} v${version} successfully!"
  echo ""
  info "Available commands:"
  echo "  /fullstack-agents:generate   - Generate entities, pages, components"
  echo "  /fullstack-agents:review     - Review code quality, security, patterns"
  echo "  /fullstack-agents:debug      - Debug errors, logs, performance"
  echo "  /fullstack-agents:analyze    - Analyze codebase and architecture"
  echo "  /fullstack-agents:scaffold   - Scaffold new projects or modules"
  echo "  /fullstack-agents:optimize   - Optimize performance and code"
  echo "  /fullstack-agents:validate   - Validate architecture patterns"
  echo "  /fullstack-agents:status     - Show project status"
}

uninstall_plugin() {
  local target="$1"
  local plugin_dest="${target}/.claude/.claude-plugins/${PLUGIN_NAME}"

  info "Uninstalling ${PLUGIN_NAME} from ${target}"

  if [[ -d "$plugin_dest" ]]; then
    rm -rf "$plugin_dest"
    ok "Removed plugin files"
  else
    warn "Plugin files not found at ${plugin_dest}"
  fi

  # Remove from settings
  local settings_file="${target}/.claude/settings.local.json"
  if [[ -f "$settings_file" ]]; then
    python3 -c "
import json
with open('${settings_file}') as f:
    s = json.load(f)
s.get('enabledPlugins', {}).pop('${PLUGIN_NAME}@local-plugins', None)
# Remove marketplace if no other plugins use it
remaining = [k for k in s.get('enabledPlugins', {}) if k.endswith('@local-plugins')]
if not remaining:
    s.get('extraKnownMarketplaces', {}).pop('local-plugins', None)
with open('${settings_file}', 'w') as f:
    json.dump(s, f, indent=2)
    f.write('\n')
" 2>/dev/null
    ok "Removed plugin from settings"
  fi

  echo ""
  ok "Uninstalled ${PLUGIN_NAME} successfully"
}

# Parse arguments
ACTION="install"
TARGET=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --uninstall|-u)
      ACTION="uninstall"
      shift
      ;;
    --version|-v)
      echo "fullstack-agents v$(get_version)"
      exit 0
      ;;
    --help|-h)
      echo "Usage: install.sh [OPTIONS] [project-path]"
      echo ""
      echo "Install or update the fullstack-agents plugin for Claude Code."
      echo ""
      echo "Options:"
      echo "  --uninstall, -u    Remove plugin from project"
      echo "  --version, -v      Show plugin version"
      echo "  --help, -h         Show this help"
      echo ""
      echo "Examples:"
      echo "  ./install.sh                          # Install to current directory"
      echo "  ./install.sh /path/to/project         # Install to specific project"
      echo "  ./install.sh --uninstall /path/to/project  # Uninstall"
      exit 0
      ;;
    *)
      TARGET="$1"
      shift
      ;;
  esac
done

# Default target is current directory
if [[ -z "$TARGET" ]]; then
  TARGET="$(pwd)"
fi

# Resolve to absolute path
TARGET="$(cd "$TARGET" 2>/dev/null && pwd)" || {
  error "Target directory does not exist: $TARGET"
  exit 1
}

case $ACTION in
  install)   install_plugin "$TARGET" ;;
  uninstall) uninstall_plugin "$TARGET" ;;
esac
