#!/bin/bash
# OPTIONAL: Register the orchestra-agent stub MCP server in your user-level
# ~/.claude/settings.json so it shows up in every Claude Code session on
# this Mac (not just the spike's test workspace).
#
# Run this if you want to feel the spike interactively — open Claude Code
# in any repo, type `/mcp`, and see `orchestra-agent` listed.
#
# This script:
#   1. Backs up your existing settings.json to settings.json.bak.<ts>
#   2. Adds `mcpServers.orchestra-agent` (without touching anything else)
#   3. Tells you where the backup lives so you can restore manually if anything breaks
#
# Use `unregister-user.sh` to cleanly remove it later.
set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"
BACKUP="$HOME/.claude/settings.json.bak.$(date +%Y%m%d%H%M%S)"
SPIKE_DIR="$(cd "$(dirname "$0")" && pwd)"
STUB="$SPIKE_DIR/../../agent/orchestra_stub_server.py"
PY="$SPIKE_DIR/../01-sdk-settingsources/.venv/bin/python"

[ -f "$SETTINGS" ] || { echo "no $SETTINGS found — is Claude Code installed?"; exit 1; }
[ -x "$PY" ] || { echo "venv python missing at $PY — run spike 01 setup first"; exit 1; }
[ -f "$STUB" ] || { echo "stub server missing at $STUB"; exit 1; }

cp "$SETTINGS" "$BACKUP"
echo "backed up to: $BACKUP"

"$PY" - <<EOF
import json, pathlib
p = pathlib.Path("$SETTINGS")
data = json.loads(p.read_text())
data.setdefault("mcpServers", {})
data["mcpServers"]["orchestra-agent"] = {
    "command": "$PY",
    "args": ["$STUB"],
}
p.write_text(json.dumps(data, indent=2))
print("orchestra-agent registered in $SETTINGS")
EOF

echo ""
echo "next: open Claude Code in any repo, type /mcp — you should see 'orchestra-agent' listed"
echo "to undo: ./unregister-user.sh  (or restore from $BACKUP)"
