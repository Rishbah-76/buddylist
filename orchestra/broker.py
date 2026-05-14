"""orchestra-poc local broker — a 60-line WebSocket message router.

Routes JSON messages between connected agents by `teamCode`. Every agent
opens an outbound WS to `ws://localhost:8765/`, sends a `hello` with its
team + display name, and then sends/receives `ask` and `answer` messages
keyed by `convId`. The broker is dumb: it knows team membership and routes
by `to`, nothing more.

Wire protocol (all messages JSON):
  hello   : { "type": "hello",  "team": str, "display": str }
  ask     : { "type": "ask",    "from": str, "to": str, "q": str, "convId": str }
  answer  : { "type": "answer", "from": str, "to": str, "a": str, "convId": str }
  error   : { "type": "error",  "convId": str | None, "reason": str }
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict

import websockets

# team_code -> { display_name -> websocket }
TEAMS: dict[str, dict[str, "websockets.ServerConnection"]] = defaultdict(dict)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


async def handler(ws) -> None:
    try:
        hello_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
    except (asyncio.TimeoutError, websockets.ConnectionClosed):
        _log("[broker] dropped connection without hello")
        return

    try:
        hello = json.loads(hello_raw)
        assert hello["type"] == "hello"
        team = str(hello["team"])
        display = str(hello["display"])
    except (json.JSONDecodeError, AssertionError, KeyError) as e:
        _log(f"[broker] malformed hello: {e}")
        await ws.send(json.dumps({"type": "error", "convId": None, "reason": f"bad hello: {e}"}))
        return

    TEAMS[team][display] = ws
    _log(f"[broker] {display}@{team} connected. team members: {list(TEAMS[team])}")
    await ws.send(json.dumps({"type": "hello-ack", "team": team, "members": list(TEAMS[team])}))

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                _log(f"[broker] {display}@{team} sent non-JSON, ignoring")
                continue

            mtype = msg.get("type")
            to = msg.get("to")
            conv = msg.get("convId")

            if mtype not in ("ask", "answer"):
                _log(f"[broker] unknown type {mtype!r} from {display}@{team}")
                continue

            target = TEAMS[team].get(to)
            if not target:
                _log(f"[broker] {mtype} from {display}@{team} -> {to!r} (not connected)")
                await ws.send(
                    json.dumps(
                        {"type": "error", "convId": conv, "reason": f"teammate {to!r} not connected"}
                    )
                )
                continue

            _log(f"[broker] route {mtype} {conv} : {display} -> {to}")
            await target.send(raw)
    except websockets.ConnectionClosed:
        pass
    finally:
        TEAMS[team].pop(display, None)
        _log(f"[broker] {display}@{team} disconnected. remaining: {list(TEAMS[team])}")


async def run(host: str = "localhost", port: int = 8765) -> None:
    _log(f"[broker] listening on ws://{host}:{port}/")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # block forever


# Back-compat alias used by the original broker/server.py script.
async def main() -> None:
    await run()


def cli_main(host: str = "localhost", port: int = 8765) -> None:
    """Entry point for `orchestra broker` (sync wrapper)."""
    try:
        asyncio.run(run(host=host, port=port))
    except KeyboardInterrupt:
        _log("[broker] shutting down")


if __name__ == "__main__":
    cli_main()
