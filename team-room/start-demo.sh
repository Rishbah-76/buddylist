#!/bin/bash
# Boots the whole orchestra-poc demo:
#   • broker on ws://localhost:8765/
#   • Bob's agent (callee, repo = playground-quickInsights)
#   • Vite dev server on http://localhost:5173/
# Writes PIDs to .demo-pids so stop-demo.sh can clean up.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
ORCHESTRA_ROOT="$(cd "$DEMO_DIR/.." && pwd)"

# Check for orchestra CLI - try multiple locations
find_orchestra() {
    # Try user local bin first
    if [ -x "$HOME/.local/bin/orchestra" ]; then
        echo "$HOME/.local/bin/orchestra"
    # Try system path
    elif command -v orchestra &>/dev/null; then
        command -v orchestra
    else
        return 1
    fi
}

ORCHESTRA=$(find_orchestra) || {
    echo "orchestra CLI not found. Install with:"
    echo "  pip install --editable $ORCHESTRA_ROOT"
    echo "  # or: uv pip install --editable $ORCHESTRA_ROOT"
    echo "Then add ~/.local/bin to your PATH:"
    echo "  export PATH=\"$HOME/.local/bin:$PATH\""
    exit 1
}

# Find Bob's config - check multiple locations
BOB_CFG=""
for cfg in "$ORCHESTRA_ROOT/spikes/04-broker-roundtrip/bob.json" \
           "$DEMO_DIR/bob.json" \
           "$ORCHESTRA_ROOT/bob.json"; do
    if [ -f "$cfg" ]; then
        BOB_CFG="$cfg"
        break
    fi
done

if [ -z "$BOB_CFG" ]; then
    echo "Bob's config not found. Looking for bob.json in:"
    echo "  $ORCHESTRA_ROOT/spikes/04-broker-roundtrip/"
    echo "  $DEMO_DIR/"
    echo "  $ORCHESTRA_ROOT/"
    exit 1
fi

# Check node_modules, install if missing
if [ ! -d "$DEMO_DIR/node_modules" ]; then
    echo "→ node_modules missing — running npm install"
    (cd "$DEMO_DIR" && npm install)
fi

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

echo "→ starting Bob's agent (config=$BOB_CFG)"
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
