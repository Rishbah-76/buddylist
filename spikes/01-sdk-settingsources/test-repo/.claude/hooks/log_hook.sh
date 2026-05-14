#!/bin/bash
# Filesystem hook: append the hook's stdin (the event JSON) to hook-log.jsonl
# Args: $1 = event name (passed by the hook config)
LOG="${CLAUDE_PROJECT_DIR:-$(pwd)}/hook-log.jsonl"
EVENT="${1:-unknown}"
INPUT=$(cat)
# Wrap each event with the event name and a timestamp so we can correlate later
printf '{"_event":"%s","_ts":"%s","payload":%s}\n' "$EVENT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$INPUT" >> "$LOG"
exit 0
