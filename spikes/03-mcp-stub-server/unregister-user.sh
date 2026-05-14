#!/bin/bash
# Remove the orchestra-agent MCP server from ~/.claude/settings.json.
# Idempotent: safe to run if it's not registered.
set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"
BACKUP="$HOME/.claude/settings.json.bak.$(date +%Y%m%d%H%M%S)"
SPIKE_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$SPIKE_DIR/../01-sdk-settingsources/.venv/bin/python"

[ -f "$SETTINGS" ] || { echo "no $SETTINGS — nothing to do"; exit 0; }

cp "$SETTINGS" "$BACKUP"
echo "backed up to: $BACKUP"

"$PY" - <<EOF
import json, pathlib
p = pathlib.Path("$SETTINGS")
data = json.loads(p.read_text())
removed = False
if isinstance(data.get("mcpServers"), dict) and "orchestra-agent" in data["mcpServers"]:
    del data["mcpServers"]["orchestra-agent"]
    if not data["mcpServers"]:
        del data["mcpServers"]
    removed = True
p.write_text(json.dumps(data, indent=2))
print("orchestra-agent removed" if removed else "orchestra-agent not present — no change")
EOF
