#!/bin/bash
# Run spike 03. Reuses the venv from spike 01.
set -euo pipefail
cd "$(dirname "$0")"
VENV=../01-sdk-settingsources/.venv/bin/python
[ -x "$VENV" ] || { echo "venv missing at $VENV — run spike 01 setup first"; exit 1; }
exec "$VENV" verify.py
