"""orchestra-poc spike #3 — does the dev's interactive Claude Code session
actually discover and call our stub MCP server?

Spike 01/02 proved the *callee* side (spawned ephemeral Claude on teammate's
repo). This spike proves the *caller* side: an interactive Claude (or anything
using the same settingSources mechanism) can find our `ask_teammate` tool
via project-level `.mcp.json` and invoke it through the real MCP protocol.

Three independent tests:
  T1 — Standalone sanity: spawn the stub directly via MCP stdio client,
       confirm it lists `ask_teammate`. Proves the server boots.
  T2 — SDK discovery via .mcp.json: SDK query() with cwd=test-workspace,
       settingSources=["project"]. Ask Claude to list tools.
       Confirms the .mcp.json registration path works.
  T3 — SDK end-to-end call: same setup, ask Claude to call
       `ask_teammate("bob", "...")`. Verify our stub's signature reply
       reaches the model AND our stub log gained an entry. Confirms
       the round-trip works without hallucination.
"""

from __future__ import annotations

import anyio
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

_dotenv_path = find_dotenv(usecwd=True)
if _dotenv_path:
    load_dotenv(_dotenv_path)

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ---- Paths ----
SPIKE_DIR = Path(__file__).parent.resolve()
ORCHESTRA_ROOT = SPIKE_DIR.parent.parent
AGENT_DIR = ORCHESTRA_ROOT / "agent"
STUB_SERVER = AGENT_DIR / "orchestra_stub_server.py"
STUB_LOG = AGENT_DIR / "stub-call-log.jsonl"
VENV_PYTHON = ORCHESTRA_ROOT / "spikes" / "01-sdk-settingsources" / ".venv" / "bin" / "python"
TEST_WORKSPACE = SPIKE_DIR / "test-workspace"
PROG_HOOK_LOG = SPIKE_DIR / "spike-prog-hook-log.jsonl"
RESULTS_PATH = SPIKE_DIR / "results.json"

STUB_REPLY_TAG = "ORCHESTRA-STUB-REPLY-v0"


# =========================================================================
# Setup / teardown
# =========================================================================


def prepare_workspace() -> None:
    """Create test-workspace/ with a .mcp.json pointing at the stub server."""
    TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)
    mcp_config = {
        "mcpServers": {
            "orchestra-agent": {
                "command": str(VENV_PYTHON),
                "args": [str(STUB_SERVER)],
            }
        }
    }
    (TEST_WORKSPACE / ".mcp.json").write_text(json.dumps(mcp_config, indent=2))
    # Also drop a minimal CLAUDE.md so the workspace looks like a project,
    # which avoids any "no project context" surprises from the SDK.
    (TEST_WORKSPACE / "CLAUDE.md").write_text(
        "# orchestra-poc test workspace\n\n"
        "This is a scratch project used only by spike #3 to verify that "
        "Claude Code picks up an MCP server registered via `.mcp.json`.\n"
    )
    # The workspace also needs a .claude dir so settingSources=["project"]
    # doesn't walk up to a parent's .claude (which we'd inherit unintentionally).
    (TEST_WORKSPACE / ".claude").mkdir(exist_ok=True)


def reset_logs() -> None:
    for p in (PROG_HOOK_LOG, STUB_LOG):
        if p.exists():
            p.unlink()


# =========================================================================
# T1 — standalone sanity via real MCP stdio client
# =========================================================================


async def t1_standalone_sanity() -> tuple[bool, str, list[str]]:
    """Spawn the stub server directly, list its tools via MCP protocol."""
    params = StdioServerParameters(
        command=str(VENV_PYTHON),
        args=[str(STUB_SERVER)],
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                names = [t.name for t in result.tools]
                ok = "ask_teammate" in names
                reason = (
                    f"tools listed: {names}"
                    if ok
                    else f"`ask_teammate` not in tool list (got {names!r})"
                )
                return ok, reason, names
    except Exception as exc:
        return False, f"stdio_client raised: {type(exc).__name__}: {exc}", []


# =========================================================================
# T2 / T3 — SDK-side hooks for observation
# =========================================================================


@dataclass
class RunOutcome:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    duration_s: float = 0.0


def _log_prog(event: str, payload: Any) -> None:
    PROG_HOOK_LOG.open("a").write(
        json.dumps(
            {
                "_event": event,
                "_ts": time.time(),
                "payload": payload if isinstance(payload, dict) else str(payload),
            },
            default=str,
        )
        + "\n"
    )


async def pre_tool_use(input_data, tool_use_id, context):
    _log_prog("PreToolUse", input_data)
    return {}


async def post_tool_use(input_data, tool_use_id, context):
    _log_prog("PostToolUse", input_data)
    return {}


def _opts() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=str(TEST_WORKSPACE),
        setting_sources=["project"],
        # Allow our MCP tool plus the few reads the model might need.
        # MCP tools surface with name pattern: mcp__<server>__<tool>
        allowed_tools=[
            "Read",
            "Grep",
            "Glob",
            "mcp__orchestra-agent__ask_teammate",
        ],
        hooks={
            "PreToolUse": [HookMatcher(matcher=None, hooks=[pre_tool_use])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[post_tool_use])],
        },
    )


async def run_prompt(prompt: str) -> RunOutcome:
    outcome = RunOutcome()
    started = time.monotonic()
    try:
        async for msg in query(prompt=prompt, options=_opts()):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        outcome.text += block.text
                    elif isinstance(block, ToolUseBlock):
                        outcome.tool_calls.append({"name": block.name, "input": block.input})
            elif isinstance(msg, ResultMessage):
                if hasattr(msg, "result") and msg.result and not outcome.text:
                    outcome.text = str(msg.result)
    except Exception as exc:
        outcome.error = f"{type(exc).__name__}: {exc}"
    outcome.duration_s = round(time.monotonic() - started, 2)
    return outcome


# =========================================================================
# Main
# =========================================================================


async def main() -> None:
    prepare_workspace()
    reset_logs()

    print("\n" + "=" * 78)
    print("orchestra-poc spike #3 — stub MCP server, caller-side verification")
    print("=" * 78)
    print(f"stub server:  {STUB_SERVER}")
    print(f"test workspace: {TEST_WORKSPACE}")
    print(f"venv python:    {VENV_PYTHON}")
    if _dotenv_path:
        print(f".env loaded:    {_dotenv_path}")
    print(f"auth route:     {'ANTHROPIC_API_KEY' if os.environ.get('ANTHROPIC_API_KEY') else 'claude CLI OAuth'}")

    results: list[dict[str, Any]] = []

    # ---------- T1 ----------
    print("\n" + "-" * 78)
    print("T1 — standalone sanity (spawn stub via real MCP stdio client)")
    print("-" * 78)
    t1_started = time.monotonic()
    t1_ok, t1_reason, tool_names = await t1_standalone_sanity()
    t1_dur = round(time.monotonic() - t1_started, 2)
    print(f"  duration: {t1_dur}s")
    print(f"  tools listed by stub: {tool_names}")
    print(f"  {'✅ PASS' if t1_ok else '❌ FAIL'}: {t1_reason}")
    results.append({"name": "standalone_sanity", "passed": t1_ok, "reason": t1_reason, "duration_s": t1_dur, "tools": tool_names})

    # ---------- T2 ----------
    print("\n" + "-" * 78)
    print("T2 — SDK discovery (project .mcp.json → ask_teammate visible to Claude)")
    print("-" * 78)
    t2 = await run_prompt(
        "Without calling any tool yet, list every MCP tool currently available "
        "to you. For each, give the exact tool name and a one-line description "
        "of what it does."
    )
    t2_mentioned = "ask_teammate" in t2.text
    print(f"  duration: {t2.duration_s}s")
    print(f"  tool_calls during T2: {[t['name'] for t in t2.tool_calls]}")
    print(f"  answer (first 500 chars): {t2.text[:500]!r}")
    t2_reason = "ask_teammate mentioned in tool listing" if t2_mentioned else f"ask_teammate NOT mentioned. error={t2.error}"
    print(f"  {'✅ PASS' if t2_mentioned else '❌ FAIL'}: {t2_reason}")
    results.append({"name": "sdk_discovery", "passed": t2_mentioned, "reason": t2_reason, "duration_s": t2.duration_s, "answer_excerpt": t2.text[:800]})

    # ---------- T3 ----------
    print("\n" + "-" * 78)
    print("T3 — SDK end-to-end call (Claude → ask_teammate → stub → reply round-trip)")
    print("-" * 78)
    t3 = await run_prompt(
        "Use the `ask_teammate` MCP tool to ask the teammate named 'bob' "
        "the question: 'what auth scheme does your /orders POST endpoint use?'. "
        "Show me bob's reply verbatim."
    )
    # Three signals it actually worked:
    invoked_via_sdk = any(tc["name"].endswith("ask_teammate") for tc in t3.tool_calls)
    stub_tag_in_text = STUB_REPLY_TAG in t3.text
    stub_log_has_entry = False
    stub_log_entry: dict[str, Any] = {}
    if STUB_LOG.exists():
        for line in STUB_LOG.read_text().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("tool") == "ask_teammate" and entry.get("teammate") == "bob":
                    stub_log_has_entry = True
                    stub_log_entry = entry
                    break
            except Exception:
                continue
    t3_ok = invoked_via_sdk and stub_tag_in_text and stub_log_has_entry
    t3_reason = (
        f"sdk_tool_call={invoked_via_sdk}, stub_tag_in_answer={stub_tag_in_text}, "
        f"stub_log_entry_present={stub_log_has_entry}"
    )
    print(f"  duration: {t3.duration_s}s")
    print(f"  tool_calls during T3: {[(t['name'], str(t['input'])[:80]) for t in t3.tool_calls]}")
    print(f"  answer (first 600 chars): {t3.text[:600]!r}")
    print(f"  stub log entry: {stub_log_entry}")
    print(f"  {'✅ PASS' if t3_ok else '❌ FAIL'}: {t3_reason}")
    results.append({
        "name": "sdk_end_to_end_call",
        "passed": t3_ok,
        "reason": t3_reason,
        "duration_s": t3.duration_s,
        "answer_excerpt": t3.text[:800],
        "stub_log_entry": stub_log_entry,
    })

    # ---------- Summary ----------
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    passed_count = sum(1 for r in results if r["passed"])
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        print(f"  {mark}  {r['name']:30s}  ({r['duration_s']}s)")
    print(f"\n{passed_count}/{len(results)} tests passed")

    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nFull results: {RESULTS_PATH}")
    print(f"Stub log:     {STUB_LOG}")
    print(f"Hook log:     {PROG_HOOK_LOG}")


if __name__ == "__main__":
    anyio.run(main)
