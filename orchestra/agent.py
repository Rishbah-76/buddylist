"""orchestra-poc local agent — the real one.

Same binary plays both roles:
  • CALLER mode (invoked with --mcp-stdio): runs as a stdio MCP server
    for the dev's Claude Code. When `ask_teammate` is called, sends an
    `ask` over WSS to the broker and waits for the matching `answer`.
  • CALLEE mode (default): just maintains the outbound WSS to the broker.
    When an incoming `ask` arrives addressed to us, spawns an Agent SDK
    `query()` in our configured repo and returns the answer.

Both modes can run in the same process — they just share the broker WS
and a pending-asks dict.

Config (JSON file passed via --config):
  {
    "display":   "alice",
    "team":      "spike04",
    "broker_url": "ws://localhost:8765/",
    "repo":      "/path/to/this/teammate's/repo"
  }
"""

from __future__ import annotations

import anyio
import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

_dotenv = find_dotenv(usecwd=False)
if _dotenv:
    load_dotenv(_dotenv)

import websockets
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Agent SDK for the callee side
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


def _err(msg: str) -> None:
    """Logging always goes to stderr — stdout is reserved for MCP JSON-RPC."""
    print(msg, file=sys.stderr, flush=True)


# ========================================================================
# Shared state between caller-side MCP loop and callee-side broker loop
# ========================================================================

PENDING_ASKS: dict[str, asyncio.Future] = {}  # convId -> Future awaiting answer
WS_LOCK = asyncio.Lock()  # serialize sends to broker
LOG_PATH = Path(__file__).parent / "agent-call-log.jsonl"


def _log(entry: dict) -> None:
    entry["ts"] = time.time()
    entry["iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ========================================================================
# Broker connection: outbound WSS, hello, then routing loop
# ========================================================================


async def connect_broker(cfg: dict) -> websockets.WebSocketClientProtocol:
    ws = await websockets.connect(cfg["broker_url"], open_timeout=5)
    await ws.send(json.dumps({"type": "hello", "team": cfg["team"], "display": cfg["display"]}))
    ack_raw = await asyncio.wait_for(ws.recv(), timeout=5)
    ack = json.loads(ack_raw)
    _err(f"[agent {cfg['display']}] connected; team members: {ack.get('members')}")
    return ws


async def broker_loop(ws, cfg: dict) -> None:
    """Receive messages from the broker.
       answer -> resolve the pending future for its convId
       ask    -> handle as callee (spawn SDK query, send answer back)"""
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")
            conv = msg.get("convId")

            if mtype == "answer":
                fut = PENDING_ASKS.pop(conv, None)
                if fut and not fut.done():
                    fut.set_result(msg.get("a", ""))
            elif mtype == "ask":
                # Callee role: spawn SDK query on our repo, send answer back
                asyncio.create_task(_handle_incoming_ask(ws, cfg, msg))
            elif mtype == "error":
                _err(f"[agent {cfg['display']}] broker error: {msg.get('reason')}")
                fut = PENDING_ASKS.pop(conv, None)
                if fut and not fut.done():
                    fut.set_exception(RuntimeError(msg.get("reason", "broker error")))
    except websockets.ConnectionClosed:
        _err(f"[agent {cfg['display']}] broker connection closed")


async def _handle_incoming_ask(ws, cfg: dict, msg: dict) -> None:
    """Callee path: someone asked us a question. Spawn SDK query in our repo."""
    question = msg.get("q", "")
    asker = msg.get("from", "unknown")
    conv = msg.get("convId")
    repo = cfg.get("repo")

    _err(f"[agent {cfg['display']}] incoming ask from {asker}: {question[:80]!r}")
    _log({"event": "incoming_ask", "from": asker, "convId": conv, "question": question[:300]})

    # Check recursion guard
    safe, reason = _check_recursion_safe(conv, asker, cfg["display"])
    if not safe:
        answer = f"[orchestra-agent] recursion blocked: {reason}. Please try again later or simplify your question."
        _log({"event": "recursion_blocked", "from": asker, "convId": conv})
        # Still send response, just with error
        async with WS_LOCK:
            await ws.send(
                json.dumps({
                    "type": "error",
                    "from": cfg["display"],
                    "to": asker,
                    "convId": conv,
                    "reason": reason,
                })
            )
        _release_conversation(conv)
        return

    if not repo or not Path(repo).exists():
        answer = f"[agent {cfg['display']}] error: my configured repo {repo!r} does not exist"
    else:
        try:
            # Load session context for better answers with prior conversation
            session_ctx = _load_session_context(asker)
            
            # Build enriched question with session context
            if session_ctx:
                full_question = (
                    f"{session_ctx}\n\n"
                    f"CURRENT QUESTION: {question}"
                )
            else:
                full_question = question
            
            answer = await _spawn_sdk_query(cfg, repo, full_question)
            
            # Save to session history for future context
            _save_session_state(asker, question, answer)
        except Exception as e:
            answer = f"[agent {cfg['display']}] error during SDK query: {type(e).__name__}: {e}"

    _log({"event": "outgoing_answer", "to": asker, "convId": conv, "answer_chars": len(answer)})

    async with WS_LOCK:
        await ws.send(
            json.dumps(
                {
                    "type": "answer",
                    "from": cfg["display"],
                    "to": asker,
                    "convId": conv,
                    "a": answer,
                }
            )
        )
    
    # Release conversation slot
    _release_conversation(conv)


# ========================================================================
# Session State Storage (for context persistence across asks)
# ========================================================================

SESSION_STATE_DIR = Path(os.path.expanduser("~/.config/orchestra-sessions"))

# In-memory session store: display_name -> list of recent Q&A pairs
SESSION_HISTORY: dict[str, list[dict]] = {}
MAX_SESSION_HISTORY = 20  # Keep last 20 questions per teammate


def _save_session_state(display: str, question: str, answer: str) -> None:
    """Persist a question-answer pair to session history."""
    if display not in SESSION_HISTORY:
        SESSION_HISTORY[display] = []
    
    SESSION_HISTORY[display].append({
        "question": question,
        "answer": answer,
        "timestamp": time.time(),
    })
    
    # Trim history
    if len(SESSION_HISTORY[display]) > MAX_SESSION_HISTORY:
        SESSION_HISTORY[display] = SESSION_HISTORY[display][-MAX_SESSION_HISTORY:]


def _load_session_context(display: str, max_questions: int = 5) -> str:
    """Load recent conversation context for a teammate."""
    if display not in SESSION_HISTORY:
        return ""
    
    history = SESSION_HISTORY[display][-max_questions:]
    context_parts = []
    for i, entry in enumerate(history, 1):
        context_parts.append(
            f"Previous Question {i}: {entry['question']}\n"
            f"Previous Answer {i}: {entry['answer'][:200]}..."
        )
    return "\n\n".join(context_parts)


# ========================================================================
# Recursion Guard (prevent ask_teammate loops)
# ========================================================================

# Track active conversations to detect potential loops
ACTIVE_CONVERSATIONS: dict[str, str] = {}  # convId -> asking teammate
CONV_CALL_DEPTH: dict[str, int] = {}  # convId -> nested call depth
MAX_CALL_DEPTH = 3  # Prevent infinite recursion


def _check_recursion_safe(convId: str, asker: str, target: str) -> tuple[bool, str]:
    """Check if this conversation would cause a recursion loop.
    
    Returns (is_safe, reason_if_blocked)
    """
    # Check if this convId already has depth tracking
    depth = CONV_CALL_DEPTH.get(convId, 0)
    
    if depth >= MAX_CALL_DEPTH:
        return False, f"Maximum recursion depth ({MAX_CALL_DEPTH}) reached"
    
    # Track this conversation
    ACTIVE_CONVERSATIONS[convId] = asker
    CONV_CALL_DEPTH[convId] = depth + 1
    
    return True, ""


def _release_conversation(convId: str) -> None:
    """Release a conversation slot after processing."""
    ACTIVE_CONVERSATIONS.pop(convId, None)
    # Don't reset depth - keeps it for audit trail


# ========================================================================
# Callee side: ephemeral SDK query in this teammate's repo
# ========================================================================

DESTRUCTIVE_BASH = (" rm ", "rm -", "rmdir ", " dd ", "mkfs", ">", "shred", "sudo ", "git push", "git reset --hard")
DENY_READ = (".env", ".credentials.json")


async def _read_only_pre_tool_use(input_data, tool_use_id, context):
    tool = input_data.get("tool_name", "")
    tinput = input_data.get("tool_input", {})
    if tool == "Bash":
        cmd = tinput.get("command", "")
        for pat in DESTRUCTIVE_BASH:
            if pat in f" {cmd} ":
                return {"decision": "block", "reason": f"orchestra-agent: destructive Bash blocked (pattern '{pat.strip()}')"}
    if tool == "Read":
        path = tinput.get("file_path", "")
        for deny in DENY_READ:
            if path.endswith(deny):
                return {"decision": "block", "reason": f"orchestra-agent: read of sensitive path '{path}' blocked"}
    return {}


async def _spawn_sdk_query(cfg: dict, repo: str, question: str) -> str:
    """Run a read-only ephemeral Claude in `repo`, with the teammate's full
    project context loaded via settingSources, and return the final answer."""
    options = ClaudeAgentOptions(
        cwd=repo,
        setting_sources=["user", "project", "local"],
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        hooks={
            "PreToolUse": [HookMatcher(matcher=None, hooks=[_read_only_pre_tool_use])],
        },
    )

    text = ""
    # The ask from a teammate should be answered concisely; nudge that.
    framed = (
        f"A teammate is asking you a quick question about this repo. "
        f"Answer concisely (5-12 sentences max) and cite specific files when relevant.\n\n"
        f"QUESTION: {question}"
    )
    async for m in query(prompt=framed, options=options):
        if isinstance(m, AssistantMessage):
            for block in m.content:
                if isinstance(block, TextBlock):
                    text += block.text
        elif isinstance(m, ResultMessage):
            if hasattr(m, "result") and m.result and not text:
                text = str(m.result)
    return text or "(no answer produced)"


# ========================================================================
# Caller side: stdio MCP server exposing `ask_teammate`
# ========================================================================

MCP_SERVER = Server("orchestra-agent")
_CFG_FOR_MCP: dict = {}
_WS_FOR_MCP: Any = None


@MCP_SERVER.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="ask_teammate",
            description=(
                "Ask another teammate's Claude a question about their service or repo. "
                "Returns the teammate's Claude's answer as a string. Use when the question "
                "is about code, decisions, or context that lives in a teammate's microservice "
                "rather than this one. Latency: ~5-15s."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "teammate's display name, e.g. 'bob'"},
                    "question": {"type": "string", "description": "the question to ask their Claude"},
                },
                "required": ["name", "question"],
            },
        )
    ]


@MCP_SERVER.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "ask_teammate":
        return [TextContent(type="text", text=f"unknown tool: {name}")]

    teammate = str(arguments.get("name", "unknown"))
    question = str(arguments.get("question", ""))
    conv = uuid.uuid4().hex

    _log({"event": "mcp_call_ask_teammate", "from": _CFG_FOR_MCP.get("display"), "to": teammate, "convId": conv, "q": question[:300]})

    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    PENDING_ASKS[conv] = fut

    if _WS_FOR_MCP is None:
        return [TextContent(type="text", text=f"[orchestra-agent] error: not connected to broker")]

    async with WS_LOCK:
        await _WS_FOR_MCP.send(
            json.dumps(
                {
                    "type": "ask",
                    "from": _CFG_FOR_MCP["display"],
                    "to": teammate,
                    "q": question,
                    "convId": conv,
                }
            )
        )

    try:
        answer = await asyncio.wait_for(fut, timeout=45)
    except asyncio.TimeoutError:
        PENDING_ASKS.pop(conv, None)
        return [TextContent(type="text", text=f"[orchestra-agent] timeout (45s) waiting for {teammate}")]
    except Exception as e:
        return [TextContent(type="text", text=f"[orchestra-agent] error: {e}")]

    _log({"event": "mcp_returned_answer", "convId": conv, "answer_chars": len(answer)})
    return [TextContent(type="text", text=answer)]


# ========================================================================
# Entrypoint
# ========================================================================


async def run_agent(cfg: dict, with_mcp_stdio: bool) -> None:
    global _WS_FOR_MCP, _CFG_FOR_MCP
    _CFG_FOR_MCP = cfg
    ws = await connect_broker(cfg)
    _WS_FOR_MCP = ws

    async def broker_task():
        await broker_loop(ws, cfg)

    async def mcp_task():
        async with stdio_server() as (read, write):
            await MCP_SERVER.run(read, write, MCP_SERVER.create_initialization_options())

    if with_mcp_stdio:
        # Run both — broker loop in background, MCP stdio in "foreground"
        async with anyio.create_task_group() as tg:
            tg.start_soon(broker_task)
            tg.start_soon(mcp_task)
    else:
        await broker_task()


def main() -> None:
    parser = argparse.ArgumentParser(description="orchestra-poc local agent")
    parser.add_argument("--config", required=True, help="path to JSON config")
    parser.add_argument("--mcp-stdio", action="store_true", help="also run an MCP stdio server (caller side)")
    args = parser.parse_args()

    cfg_path = Path(args.config).expanduser().resolve()
    cfg = json.loads(cfg_path.read_text())
    _err(f"[agent {cfg['display']}] starting (mcp_stdio={args.mcp_stdio})  config={cfg_path}")
    anyio.run(run_agent, cfg, args.mcp_stdio)


if __name__ == "__main__":
    main()
