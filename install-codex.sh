#!/usr/bin/env bash
# Independent Codex installation; never invokes or changes the Claude installer.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$here/integrations/codex/scripts/install.py" "$@"
