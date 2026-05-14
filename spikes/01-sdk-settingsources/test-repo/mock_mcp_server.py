"""Tiny stdio MCP server used by the orchestra-poc spike to verify that
the Agent SDK's settingSources picks up the project's .mcp.json and starts
the configured servers.

Exposes one tool: `mock_get_status`. The tool returns a known fingerprint
string. The spike script checks whether Claude invoked this tool and got
the fingerprint back.
"""

from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

MCP_FINGERPRINT = "MCP-FINGERPRINT-ECHO-IOTA-77"

server: Server = Server("orders-status-mock")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="mock_get_status",
            description=(
                "Return the current operational status of Bob's orders service. "
                "Useful when a teammate wants to know if the service is up."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "mock_get_status":
        body = (
            f"status=healthy, qps=12, p99_ms=180, fingerprint={MCP_FINGERPRINT}"
        )
        return [TextContent(type="text", text=body)]
    return [TextContent(type="text", text=f"unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
