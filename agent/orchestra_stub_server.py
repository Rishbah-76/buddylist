"""orchestra-agent — stub MCP server.

Exposes one tool: `ask_teammate(name, question)`. The tool's job in the real
agent will be to route the question through the broker to the named teammate's
local agent, which spawns a Claude SDK `query()` in their repo and streams
the answer back. For now, returns a hardcoded reply so we can prove the
wiring works end-to-end without any networking or broker.

Every call is appended to `stub-call-log.jsonl` in this directory so
verification scripts can confirm the tool was actually invoked (not just
hallucinated by the model).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

LOG_FILE = Path(__file__).parent / "stub-call-log.jsonl"
STUB_TAG = "ORCHESTRA-STUB-REPLY-v0"

server: Server = Server("orchestra-agent")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ask_teammate",
            description=(
                "Ask another teammate's Claude a question about their service "
                "or repo. Returns a string answer with the teammate's name and "
                "a short reply. Use when you need context about code or "
                "decisions that live in a teammate's microservice."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "teammate's display name, e.g. 'bob'",
                    },
                    "question": {
                        "type": "string",
                        "description": "the question to ask their Claude",
                    },
                },
                "required": ["name", "question"],
            },
        )
    ]


def _log(entry: dict) -> None:
    entry["ts"] = time.time()
    entry["iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Logging is best-effort; never crash the server because we couldn't log
        pass


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "ask_teammate":
        teammate = str(arguments.get("name", "unknown"))
        question = str(arguments.get("question", ""))
        _log({"tool": name, "teammate": teammate, "question": question[:500]})
        reply = (
            f"[{STUB_TAG}] from teammate={teammate!r}: I received your question "
            f"{question!r}. The real implementation will route this through the "
            f"broker to {teammate}'s local agent, which spawns a Claude SDK "
            f"query() in their repo and streams the answer back. For now, "
            f"this is a hardcoded acknowledgement."
        )
        return [TextContent(type="text", text=reply)]

    _log({"tool": name, "error": "unknown tool"})
    return [TextContent(type="text", text=f"unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
