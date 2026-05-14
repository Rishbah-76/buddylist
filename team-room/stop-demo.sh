#!/bin/bash
# Stop the demo cleanly using PIDs recorded by start-demo.sh.
set -euo pipefail
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DEMO_DIR/.demo-pids"

if [ ! -f "$PID_FILE" ]; then
  echo "no .demo-pids found; nothing to do"
  # belt-and-suspenders: kill anything on the demo ports/scripts
  pkill -f "broker/server.py" 2>/dev/null || true
  pkill -f "orchestra_agent.py" 2>/dev/null || true
  lsof -ti:8765,5173 2>/dev/null | xargs -r kill -9 2>/dev/null || true
  exit 0
fi

for pid in $(cat "$PID_FILE"); do
  if kill -0 "$pid" 2>/dev/null; then
    echo "→ stopping pid $pid"
    kill "$pid" 2>/dev/null || true
  fi
done
# Vite often spawns a child node process; clean it up too
pkill -f "vite --port 5173" 2>/dev/null || true
rm -f "$PID_FILE"
echo "stopped."
