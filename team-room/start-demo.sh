#!/bin/bash
# Boots the whole orchestra-poc demo:
#   • broker on ws://localhost:8765/
#   • Bob's agent (callee, repo = playground-quickInsights)
#   • Vite dev server on http://localhost:5173/
# Writes PIDs to .demo-pids so stop-demo.sh can clean up.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
ORCHESTRA_ROOT="$(cd "$DEMO_DIR/.." && pwd)"
VENV_BIN="$ORCHESTRA_ROOT/spikes/01-sdk-settingsources/.venv/bin"
ORCHESTRA="$VENV_BIN/orchestra"
BOB_CFG="$ORCHESTRA_ROOT/spikes/04-broker-roundtrip/bob.json"

[ -x "$VENV_BIN/python" ] || { echo "venv missing at $VENV_BIN — run spike 01 setup first"; exit 1; }
[ -x "$ORCHESTRA" ] || { echo "orchestra CLI missing — run: cd $ORCHESTRA_ROOT && uv pip install --python $VENV_BIN/python --editable ."; exit 1; }
[ -d "$DEMO_DIR/node_modules" ] || { echo "node_modules missing — running npm install"; (cd "$DEMO_DIR" && npm install); }

# Clean any old PIDs from a stale run
if [ -f "$DEMO_DIR/.demo-pids" ]; then
  echo "→ found stale .demo-pids, stopping old processes first…"
  "$DEMO_DIR/stop-demo.sh" || true
fi

mkdir -p "$DEMO_DIR/logs"
echo "→ starting broker on :8765"
nohup "$ORCHESTRA" broker > "$DEMO_DIR/logs/broker.log" 2>&1 &
BROKER_PID=$!
sleep 1

echo "→ starting Bob's agent (repo=playground-quickInsights)"
nohup "$ORCHESTRA" agent --config "$BOB_CFG" > "$DEMO_DIR/logs/bob.log" 2>&1 &
BOB_PID=$!
sleep 1

echo "→ starting Vite dev server on :5173"
cd "$DEMO_DIR" && nohup npm run dev > "$DEMO_DIR/logs/vite.log" 2>&1 &
VITE_PID=$!

echo "$BROKER_PID $BOB_PID $VITE_PID" > "$DEMO_DIR/.demo-pids"

sleep 3
echo ""
echo "──────────────────────────────────────────────────────────────────────"
echo "  orchestra-poc demo running."
echo "  open: http://localhost:5173/?team=spike04-test&name=rishabh-ui"
echo "──────────────────────────────────────────────────────────────────────"
echo "  PIDs: broker=$BROKER_PID  bob=$BOB_PID  vite=$VITE_PID"
echo "  logs: $DEMO_DIR/logs/"
echo "  stop: $DEMO_DIR/stop-demo.sh"
echo "──────────────────────────────────────────────────────────────────────"
