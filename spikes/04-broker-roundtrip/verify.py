"""orchestra-poc spike #4 — end-to-end broker round-trip.

Spins up:
  1. The local WS broker  (ws://localhost:8765/)
  2. Bob's agent — connected to broker, configured with the real
     playground-quickInsights repo as its callee repo.
  3. An SDK query() (proxying for Alice's Claude Code), with a project
     `.mcp.json` that launches Alice's agent as a subprocess. Alice's
     agent ALSO connects to the same broker.

Then asks Claude to call `ask_teammate("bob", "<real question about Bob's repo>")`
and verifies the answer references content that only exists in Bob's real repo
(Thout pipeline / 4-pass / Goldstar terminology). This means the round-trip
A→broker→B→SDK-query-on-Bob's-repo→broker→A actually worked.

Concurrent processes:
  - broker.subprocess (orchestra-poc/broker/server.py)
  - bob.subprocess    (orchestra-poc/agent/orchestra_agent.py --config bob.json)
  - alice.subprocess  (spawned BY Claude as Alice's MCP server, --mcp-stdio)
"""

from __future__ import annotations

import anyio
import json
import os
import signal
import subprocess
import sys
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


# ---- Paths ----
SPIKE_DIR = Path(__file__).parent.resolve()
ORCHESTRA_ROOT = SPIKE_DIR.parent.parent
BROKER = ORCHESTRA_ROOT / "broker" / "server.py"
AGENT = ORCHESTRA_ROOT / "agent" / "orchestra_agent.py"
AGENT_LOG = ORCHESTRA_ROOT / "agent" / "agent-call-log.jsonl"
VENV_PY = ORCHESTRA_ROOT / "spikes" / "01-sdk-settingsources" / ".venv" / "bin" / "python"

ALICE_WORKSPACE = SPIKE_DIR / "alice-workspace"
BROKER_LOG = SPIKE_DIR / "broker.log"
BOB_LOG = SPIKE_DIR / "bob.log"
ALICE_LOG = SPIKE_DIR / "alice.log"  # written by alice's stderr when SDK spawns it
RESULTS = SPIKE_DIR / "results.json"


# ========================================================================
# Workspace setup — Alice's workspace points the MCP server at our agent
# ========================================================================


def prepare_alice_workspace() -> None:
    ALICE_WORKSPACE.mkdir(parents=True, exist_ok=True)
    alice_cfg = SPIKE_DIR / "alice.json"
    (ALICE_WORKSPACE / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "orchestra-agent": {
                        "command": str(VENV_PY),
                        "args": [
                            str(AGENT),
                            "--config",
                            str(alice_cfg),
                            "--mcp-stdio",
                        ],
                        "env": {
                            # Forward the SDK auth to Alice's spawned agent
                            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
                            # Mark Alice's stderr destination so we can correlate logs
                            "ORCHESTRA_AGENT_ROLE": "alice",
                        },
                    }
                }
            },
            indent=2,
        )
    )
    (ALICE_WORKSPACE / "CLAUDE.md").write_text(
        "# Alice's tiny workspace\n\nThis is just where Alice's Claude lives. "
        "Bob's real repo lives elsewhere.\n"
    )
    (ALICE_WORKSPACE / ".claude").mkdir(exist_ok=True)


# ========================================================================
# Subprocess management
# ========================================================================


def start_subprocess(cmd: list[str], log_path: Path, label: str) -> subprocess.Popen:
    f = log_path.open("w")
    proc = subprocess.Popen(
        cmd,
        stdout=f,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    print(f"  started {label} pid={proc.pid}  → log {log_path}")
    return proc


def wait_for_log_marker(log_path: Path, marker: str, timeout: float = 8.0) -> bool:
    """Block until `marker` appears in log_path or timeout."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if log_path.exists() and marker in log_path.read_text():
            return True
        time.sleep(0.2)
    return False


def stop_subprocess(proc: subprocess.Popen, label: str) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print(f"  stopped {label}")


# ========================================================================
# Drive the SDK query (Alice's Claude proxy)
# ========================================================================


@dataclass
class RunOutcome:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    duration_s: float = 0.0


async def run_alice_query(prompt: str) -> RunOutcome:
    options = ClaudeAgentOptions(
        cwd=str(ALICE_WORKSPACE),
        setting_sources=["project"],
        allowed_tools=["mcp__orchestra-agent__ask_teammate", "Read", "Grep", "Glob"],
    )
    outcome = RunOutcome()
    started = time.monotonic()
    try:
        async for m in query(prompt=prompt, options=options):
            if isinstance(m, AssistantMessage):
                for block in m.content:
                    if isinstance(block, TextBlock):
                        outcome.text += block.text
                    elif isinstance(block, ToolUseBlock):
                        outcome.tool_calls.append({"name": block.name, "input": block.input})
            elif isinstance(m, ResultMessage):
                if hasattr(m, "result") and m.result and not outcome.text:
                    outcome.text = str(m.result)
    except Exception as e:
        outcome.error = f"{type(e).__name__}: {e}"
    outcome.duration_s = round(time.monotonic() - started, 2)
    return outcome


# ========================================================================
# Main
# ========================================================================


async def amain() -> int:
    print("\n" + "=" * 78)
    print("orchestra-poc spike #4 — broker round-trip (local)")
    print("=" * 78)
    print(f"broker:         {BROKER}")
    print(f"agent:          {AGENT}")
    print(f"alice workspace:{ALICE_WORKSPACE}")
    print(f"bob's REAL repo:/Users/rishabh/Desktop/playground-quickInsights")
    print(f".env loaded:    {_dotenv_path}")
    print(f"auth route:     {'ANTHROPIC_API_KEY' if os.environ.get('ANTHROPIC_API_KEY') else 'OAuth'}")

    # Clear logs from previous run
    for p in (BROKER_LOG, BOB_LOG, ALICE_LOG, AGENT_LOG):
        if p.exists():
            p.unlink()
    prepare_alice_workspace()

    procs: list[tuple[subprocess.Popen, str]] = []
    results: dict[str, Any] = {}

    try:
        # ---------- 1. Start broker ----------
        print("\n[1/3] starting broker")
        broker = start_subprocess(
            [str(VENV_PY), str(BROKER)],
            BROKER_LOG,
            "broker",
        )
        procs.append((broker, "broker"))
        if not wait_for_log_marker(BROKER_LOG, "listening on ws://"):
            print("❌ broker did not come up; aborting")
            print(BROKER_LOG.read_text() if BROKER_LOG.exists() else "(no broker log)")
            return 1
        print("  ✅ broker up")

        # ---------- 2. Start Bob's agent ----------
        print("\n[2/3] starting bob's agent (callee-only, no MCP stdio)")
        bob = start_subprocess(
            [str(VENV_PY), str(AGENT), "--config", str(SPIKE_DIR / "bob.json")],
            BOB_LOG,
            "bob",
        )
        procs.append((bob, "bob"))
        if not wait_for_log_marker(BOB_LOG, "[agent bob] connected"):
            print("❌ bob's agent did not connect to broker")
            print(BOB_LOG.read_text() if BOB_LOG.exists() else "(no bob log)")
            return 1
        print("  ✅ bob connected to broker")

        # Sanity check the broker is now showing both will-be members of the team
        # (alice connects lazily when the SDK query spawns her — broker log
        # will show that at query time)
        print(f"  broker log so far:\n    " + "\n    ".join(BROKER_LOG.read_text().splitlines()[-3:]))

        # ---------- 3. Drive Alice's Claude via SDK ----------
        print("\n[3/3] driving Alice's Claude — calling ask_teammate('bob', <real question>)")
        prompt = (
            "Use the `ask_teammate` MCP tool to ask the teammate named 'bob' "
            "this exact question: 'In your repo, what are the four passes of "
            "the LLM pipeline? Just name each pass briefly.' Then show me bob's "
            "answer verbatim."
        )
        outcome = await run_alice_query(prompt)
        print(f"  duration: {outcome.duration_s}s")
        print(f"  tool_calls: {[(t['name'], str(t['input'])[:90]) for t in outcome.tool_calls]}")
        print(f"  answer (first 800 chars):\n    {outcome.text[:800]!r}")

        # ---------- Validate ----------
        sdk_called_tool = any(t["name"].endswith("ask_teammate") for t in outcome.tool_calls)
        bobs_real_content = any(
            kw in outcome.text.lower()
            for kw in ["semantic", "structured", "diagnostic", "synthesis", "pass 1", "pass 2", "pass 3", "pass 4"]
        )
        # Verify Bob's agent log actually saw an incoming ask and produced an answer
        agent_log_text = AGENT_LOG.read_text() if AGENT_LOG.exists() else ""
        bob_received_ask = '"event": "incoming_ask"' in agent_log_text
        bob_sent_answer = '"event": "outgoing_answer"' in agent_log_text
        broker_routed = "route ask" in BROKER_LOG.read_text() and "route answer" in BROKER_LOG.read_text()

        all_signals = {
            "alice_sdk_called_ask_teammate": sdk_called_tool,
            "broker_routed_both_directions": broker_routed,
            "bob_received_ask": bob_received_ask,
            "bob_sent_answer": bob_sent_answer,
            "answer_references_real_bob_repo_content": bobs_real_content,
            "no_sdk_error": outcome.error == "",
        }
        passed = all(all_signals.values())
        print("\nverification signals:")
        for k, v in all_signals.items():
            mark = "✅" if v else "❌"
            print(f"    {mark}  {k}")

        results = {
            "passed": passed,
            "signals": all_signals,
            "duration_s": outcome.duration_s,
            "tool_calls": outcome.tool_calls,
            "answer_excerpt": outcome.text[:1200],
            "error": outcome.error,
            "agent_log_tail": agent_log_text.splitlines()[-15:],
            "broker_log_tail": BROKER_LOG.read_text().splitlines()[-15:],
            "bob_log_tail": BOB_LOG.read_text().splitlines()[-15:] if BOB_LOG.exists() else [],
        }

        print("\n" + "=" * 78)
        print("SUMMARY")
        print("=" * 78)
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}  end_to_end_broker_roundtrip  ({outcome.duration_s}s)")
        RESULTS.write_text(json.dumps(results, indent=2, default=str))
        print(f"\nFull results: {RESULTS}")
        return 0 if passed else 1
    finally:
        # Tear down in reverse order
        print("\n[teardown]")
        for proc, label in reversed(procs):
            stop_subprocess(proc, label)


if __name__ == "__main__":
    sys.exit(anyio.run(amain))
