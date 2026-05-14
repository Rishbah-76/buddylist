"""Orchestra CLI — single entry point with subcommands.

  orchestra broker [--port 8765] [--host localhost] [--tunnel]
  orchestra tunnel [--target http://localhost:8765]
  orchestra agent  --config X.json
  orchestra agent  --team T --as N --broker URL --repo PATH [--mcp-stdio]

Run `orchestra <cmd> --help` for details.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import anyio


def _import_agent():
    # Local import so `--help` and `broker/tunnel` don't pay the SDK import cost.
    from . import agent as agent_mod

    return agent_mod


def _import_broker():
    from . import broker as broker_mod

    return broker_mod


def _import_tunnel():
    from . import tunnel as tunnel_mod

    return tunnel_mod


# ───────────────────────────── broker ─────────────────────────────


def cmd_broker(args: argparse.Namespace) -> int:
    broker = _import_broker()
    if args.tunnel:
        # Run the broker in a daemon thread; tunnel takes the foreground.
        tunnel = _import_tunnel()

        def _broker_thread():
            try:
                asyncio.run(broker.run(host=args.host, port=args.port))
            except KeyboardInterrupt:
                pass

        t = threading.Thread(target=_broker_thread, daemon=True)
        t.start()
        # Give the broker a moment to bind before we hand off to cloudflared.
        import time as _t
        _t.sleep(1.0)
        return tunnel.run_tunnel(f"http://{args.host}:{args.port}")
    broker.cli_main(host=args.host, port=args.port)
    return 0


# ───────────────────────────── tunnel ─────────────────────────────


def cmd_tunnel(args: argparse.Namespace) -> int:
    tunnel = _import_tunnel()
    return tunnel.run_tunnel(args.target)


# ───────────────────────────── agent ──────────────────────────────


def cmd_agent(args: argparse.Namespace) -> int:
    agent = _import_agent()

    if args.config:
        cfg_path = Path(args.config).expanduser().resolve()
        cfg = json.loads(cfg_path.read_text())
        # Allow inline overrides
        if args.as_: cfg["display"] = args.as_
        if args.team: cfg["team"] = args.team
        if args.broker: cfg["broker_url"] = args.broker
        if args.repo: cfg["repo"] = str(Path(args.repo).expanduser().resolve())
    else:
        missing = [
            flag
            for flag, val in {
                "--team": args.team,
                "--as": args.as_,
                "--broker": args.broker,
                "--repo": args.repo,
            }.items()
            if not val
        ]
        if missing:
            sys.exit(
                f"error: when --config is omitted you must pass {', '.join(missing)} "
                "(or pass --config <path>.json)"
            )
        cfg = {
            "display": args.as_,
            "team": args.team,
            "broker_url": args.broker,
            "repo": str(Path(args.repo).expanduser().resolve()),
        }

    print(
        f"[agent {cfg['display']}] starting  team={cfg['team']}  broker={cfg['broker_url']}  "
        f"repo={cfg['repo']}  mcp_stdio={args.mcp_stdio}",
        file=sys.stderr,
        flush=True,
    )
    try:
        anyio.run(agent.run_agent, cfg, args.mcp_stdio)
    except KeyboardInterrupt:
        print(f"[agent {cfg['display']}] stopped", file=sys.stderr)
    return 0


# ───────────────────────────── parser ─────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="orchestra",
        description="Federated Claude Code session orchestration.",
    )
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<command>")

    pb = sub.add_parser("broker", help="Run the team broker (WebSocket router)")
    pb.add_argument("--host", default="localhost")
    pb.add_argument("--port", type=int, default=8765)
    pb.add_argument(
        "--tunnel",
        action="store_true",
        help="Also start a Cloudflare quick tunnel and print the public WSS URL",
    )
    pb.set_defaults(func=cmd_broker)

    pt = sub.add_parser("tunnel", help="Expose a local URL via Cloudflare quick tunnel")
    pt.add_argument("--target", default="http://localhost:8765")
    pt.set_defaults(func=cmd_tunnel)

    pa = sub.add_parser(
        "agent",
        help="Run the orchestra agent (callee + optional MCP-stdio caller)",
    )
    pa.add_argument("--config", help="Path to JSON config (legacy / power-user)")
    pa.add_argument("--team", help="Team code (shared secret)")
    pa.add_argument("--as", dest="as_", metavar="NAME", help="Your display name in the team")
    pa.add_argument("--broker", help="Broker URL, e.g. wss://xyz.trycloudflare.com/")
    pa.add_argument("--repo", help="Path to the repo this agent should expose")
    pa.add_argument(
        "--mcp-stdio",
        action="store_true",
        help="Also expose ask_teammate to this machine's Claude Code via MCP stdio",
    )
    pa.set_defaults(func=cmd_agent)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
