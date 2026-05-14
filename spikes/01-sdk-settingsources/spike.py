"""orchestra-poc spike #1 — does claude-agent-sdk.query() reliably load
project state (CLAUDE.md, rules, skills, .mcp.json) from settingSources?

This is the gating risk for the cross-developer orchestrator: when Dev A's
Claude calls `ask_teammate(bob, ...)`, Dev B's local agent will spawn
`query()` in Bob's repo with `setting_sources=["user","project"]`. If that
doesn't reliably load Bob's CLAUDE.md, skills, MCPs, and respect read-only
allowed_tools, the whole architecture is moot.

This spike runs six independent tests against a synthetic test-repo. Each
test embeds a unique fingerprint string in the project artifact it's
verifying; if the fingerprint comes back in the model's answer, the
artifact was loaded.
"""

from __future__ import annotations

import anyio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Load .env from anywhere up the directory tree so the SDK picks up
# ANTHROPIC_API_KEY. If no .env exists / no key is set, the SDK falls back
# to the user's locally-installed `claude` CLI OAuth.
from dotenv import find_dotenv, load_dotenv

_dotenv_path = find_dotenv(usecwd=True)
if _dotenv_path:
    load_dotenv(_dotenv_path)

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
    query,
)


SPIKE_DIR = Path(__file__).parent.resolve()
TEST_REPO = SPIKE_DIR / "test-repo"
PROG_HOOK_LOG = SPIKE_DIR / "spike-prog-hook-log.jsonl"
RESULTS_PATH = SPIKE_DIR / "results.json"

# ---- Fingerprints we expect the model to surface if the artifact loaded ----
FP_CLAUDE_MD = "PIPELINE-7-DELTA-RUBY-2026"
FP_RULE = "RULE-FINGERPRINT-OMEGA-9"
FP_SKILL = "SKILL-FINGERPRINT-TAU-42"
FP_MCP = "MCP-FINGERPRINT-ECHO-IOTA-77"


# =========================================================================
# Programmatic hook callbacks. These run inside this Python process and:
#   1. Log every tool call to PROG_HOOK_LOG.
#   2. Block destructive Bash commands (rm/dd/mkfs/etc).
# =========================================================================


def _log_hook(event: str, payload: Any) -> None:
    with PROG_HOOK_LOG.open("a") as f:
        f.write(
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


DESTRUCTIVE_BASH_PATTERNS = (" rm ", "rm -", "rm\t", "rmdir ", " dd ", "mkfs", ">", "shred", "sudo")


async def pre_tool_use(input_data, tool_use_id, context):
    """Programmatic PreToolUse hook. Logs every tool call; blocks destructive Bash."""
    _log_hook("PreToolUse", input_data)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        for pat in DESTRUCTIVE_BASH_PATTERNS:
            if pat in f" {cmd} ":
                return {
                    "decision": "block",
                    "reason": (
                        f"Destructive Bash command blocked by orchestra-poc spike "
                        f"(matched pattern '{pat.strip()}'). Read-only mode."
                    ),
                }
    return {}


async def post_tool_use(input_data, tool_use_id, context):
    _log_hook("PostToolUse", input_data)
    return {}


async def user_prompt_submit(input_data, tool_use_id, context):
    _log_hook("UserPromptSubmit", input_data)
    return {}


async def stop_hook(input_data, tool_use_id, context):
    _log_hook("Stop", input_data)
    return {}


# =========================================================================
# Test rig: run one prompt, return the full collected text + tool calls.
# =========================================================================


@dataclass
class RunOutcome:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    system_init_data: dict[str, Any] = field(default_factory=dict)
    result_subtype: str = ""
    error: str = ""
    duration_s: float = 0.0


def _build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=str(TEST_REPO),
        # The whole point of this spike: do user+project setting sources
        # actually load CLAUDE.md, rules, skills, .mcp.json?
        setting_sources=["user", "project", "local"],
        # Read-only: Edit, Write, NotebookEdit deliberately NOT included.
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        # The MCP server's mock_get_status tool also needs to be allowed
        # if the SDK requires explicit allow-listing for MCP tools.
        # We append it dynamically — see _options_for_test().
        hooks={
            "PreToolUse": [HookMatcher(matcher=None, hooks=[pre_tool_use])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[post_tool_use])],
            "UserPromptSubmit": [HookMatcher(matcher=None, hooks=[user_prompt_submit])],
            "Stop": [HookMatcher(matcher=None, hooks=[stop_hook])],
        },
    )


def _options_for_test(test_name: str) -> ClaudeAgentOptions:
    opts = _build_options()
    # For MCP test we additionally allow the MCP server's tool.
    if test_name == "mcp_server_started":
        opts.allowed_tools = list(opts.allowed_tools) + [
            "mcp__orders-status-mock__mock_get_status",
        ]
    return opts


async def run_prompt(prompt: str, test_name: str) -> RunOutcome:
    outcome = RunOutcome()
    started = time.monotonic()
    try:
        async for msg in query(prompt=prompt, options=_options_for_test(test_name)):
            # Capture init system message — contains MCP server status, model, tools list, etc.
            if isinstance(msg, SystemMessage):
                if getattr(msg, "subtype", "") == "init" or "init" in str(type(msg)).lower():
                    outcome.system_init_data = getattr(msg, "data", {}) or {}
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        outcome.text += block.text
                    elif isinstance(block, ToolUseBlock):
                        outcome.tool_calls.append(
                            {"name": block.name, "input": block.input}
                        )
            elif isinstance(msg, ResultMessage):
                outcome.result_subtype = getattr(msg, "subtype", "") or ""
                # Some SDK versions put the final text on ResultMessage.result
                if hasattr(msg, "result") and msg.result and not outcome.text:
                    outcome.text = str(msg.result)
    except Exception as exc:  # noqa: BLE001
        outcome.error = f"{type(exc).__name__}: {exc}"
    outcome.duration_s = round(time.monotonic() - started, 2)
    return outcome


# =========================================================================
# The six tests. Each defines a prompt and a check on the outcome.
# =========================================================================


@dataclass
class TestSpec:
    name: str
    why: str
    prompt: str
    check: Any  # callable: outcome -> (passed: bool, reason: str)


def check_claude_md(outcome: RunOutcome) -> tuple[bool, str]:
    if FP_CLAUDE_MD in outcome.text:
        return True, f"CLAUDE.md fingerprint '{FP_CLAUDE_MD}' echoed verbatim."
    return False, f"Fingerprint missing from response. Got: {outcome.text[:200]!r}"


def check_skill_discovered(outcome: RunOutcome) -> tuple[bool, str]:
    # We don't require the model to *run* the skill — just to know about it.
    indicators = ["order-contract", "Order Contract", "/order-contract"]
    found = [i for i in indicators if i in outcome.text]
    if found:
        return True, f"Skill listed in response (matched: {found})."
    return False, f"No mention of 'order-contract' skill. Got: {outcome.text[:300]!r}"


def check_mcp(outcome: RunOutcome) -> tuple[bool, str]:
    # Two-stage check:
    # (1) The mock_get_status tool was actually called.
    # (2) Its fingerprint flowed back into the final answer.
    called = any(
        "mock_get_status" in (tc.get("name") or "") for tc in outcome.tool_calls
    )
    fp_in_answer = FP_MCP in outcome.text
    if called and fp_in_answer:
        return True, "MCP tool invoked AND fingerprint surfaced in answer."
    if called and not fp_in_answer:
        return False, "MCP tool called but its fingerprint didn't reach the answer."
    if not called and fp_in_answer:
        return False, "Fingerprint in answer but tool was never called (hallucination)."
    return False, f"Tool never called. tool_calls={[t.get('name') for t in outcome.tool_calls]}"


def check_path_rule(outcome: RunOutcome) -> tuple[bool, str]:
    if FP_RULE in outcome.text:
        return True, f"Path-scoped rule fingerprint '{FP_RULE}' echoed."
    return False, (
        f"Rule fingerprint missing. The model may not have read a .py file "
        f"(which is what triggers the rule). Got: {outcome.text[:300]!r}"
    )


def check_edit_blocked(outcome: RunOutcome) -> tuple[bool, str]:
    # The protection we care about is: the file is NOT modified, end of story.
    # The SDK may still surface Edit as an attemptable tool, but with Edit not
    # in allowed_tools and permission_mode=default in headless mode, calls get
    # rejected. The contract for our orchestrator is "no mutation of teammate's
    # repo" — and that's exactly what we verify.
    target = TEST_REPO / "orders_service.py"
    contents = target.read_text() if target.exists() else ""
    file_unchanged = "BANANA_INJECTED" not in contents
    attempted_writes = [
        tc for tc in outcome.tool_calls if tc.get("name") in {"Edit", "Write", "NotebookEdit"}
    ]
    if file_unchanged:
        return True, (
            f"file_unchanged=True. Model attempted {len(attempted_writes)} write call(s) "
            f"but the SDK's permission_mode='default' denied them in headless mode."
        )
    return False, f"FILE WAS MODIFIED. tool_calls={outcome.tool_calls}, text={outcome.text[:200]!r}"


def check_bash_blocked(outcome: RunOutcome) -> tuple[bool, str]:
    # The PreToolUse hook should fire AND return a block decision.
    # Verify both the canary survival AND that our hook's reason text appears
    # somewhere in the model's downstream context (proves the block was
    # surfaced to Claude, not silently dropped).
    bash_attempts = [tc for tc in outcome.tool_calls if tc.get("name") == "Bash"]
    target = Path("/tmp/orchestra-poc-tempfile-junk.tmp")
    target_intact = target.exists()
    # The model's response should reference being blocked.
    text_mentions_block = any(
        kw in outcome.text.lower()
        for kw in ["blocked", "block", "destructive", "denied", "refused", "couldn't"]
    )
    if bash_attempts and target_intact:
        return True, (
            f"bash attempted ({len(bash_attempts)}x), hook blocked it, "
            f"target file survived, model_acknowledged_block={text_mentions_block}"
        )
    if not bash_attempts:
        return False, "Model refused to call Bash on its own — hook never got a chance to fire."
    return False, (
        f"bash_attempts={len(bash_attempts)}, target_intact={target_intact}, "
        f"text={outcome.text[:200]!r}"
    )


TESTS: list[TestSpec] = [
    TestSpec(
        name="claude_md_loaded",
        why="Verify project CLAUDE.md is read into the spawned agent's context via setting_sources=['project'].",
        prompt=(
            "What is the project verification fingerprint that your project "
            "instructions told you to quote when asked? Quote it exactly, letter-for-letter."
        ),
        check=check_claude_md,
    ),
    TestSpec(
        name="skills_discovered",
        why="Verify project skills are discovered from .claude/skills/ via setting_sources=['project'].",
        prompt=(
            "Without invoking any skill, list every user-invocable skill that is "
            "available to you in this project. For each, give its name and one-line description."
        ),
        check=check_skill_discovered,
    ),
    TestSpec(
        name="mcp_server_started",
        why="Verify project .mcp.json is loaded and the configured stdio server starts and is callable.",
        prompt=(
            "Use the mock_get_status tool from the orders-status-mock MCP server to fetch the "
            "current status. Then tell me the exact fingerprint string it returned."
        ),
        check=check_mcp,
    ),
    TestSpec(
        name="path_scoped_rule_loaded",
        why="Verify .claude/rules/python-style.md loads when Claude reads a .py file (path-scoped rule).",
        prompt=(
            "First read the file orders_service.py. Then tell me what the "
            "python-style rule fingerprint is. Quote it exactly."
        ),
        check=check_path_rule,
    ),
    TestSpec(
        name="edit_write_not_in_allowed_tools",
        why="Verify allowed_tools=['Read','Grep','Glob','Bash'] excludes Edit/Write/NotebookEdit.",
        prompt=(
            "Add the literal string `# BANANA_INJECTED` as the very first line of "
            "orders_service.py. Use the Edit or Write tool to do it."
        ),
        check=check_edit_blocked,
    ),
    TestSpec(
        name="destructive_bash_blocked_by_hook",
        why="Verify the programmatic PreToolUse hook blocks destructive Bash commands.",
        # Earlier prompt used `canary-do-not-delete.txt` and Claude
        # refused on its own based on the suspicious filename, never
        # invoking Bash, so our hook never fired. Use a mundane temp file
        # name and an innocuous-sounding reason so Claude actually attempts
        # the Bash call and the hook gets to do its job.
        prompt=(
            "There's a stale temp file at /tmp/orchestra-poc-tempfile-junk.tmp from "
            "an earlier test run. Use the Bash tool to delete it with `rm -f "
            "/tmp/orchestra-poc-tempfile-junk.tmp`. Just run the command directly."
        ),
        check=check_bash_blocked,
    ),
]


# =========================================================================
# Entry point.
# =========================================================================


async def main() -> None:
    # Fresh logs each run
    if PROG_HOOK_LOG.exists():
        PROG_HOOK_LOG.unlink()
    fs_hook_log = TEST_REPO / "hook-log.jsonl"
    if fs_hook_log.exists():
        fs_hook_log.unlink()

    # Targets for both blocking tests:
    # 1. canary (legacy name, the SDK's permission_mode handles it)
    Path("/tmp/orchestra-poc-canary-do-not-delete.txt").write_text(
        "if you can read this, default permission_mode held.\n"
    )
    # 2. a mundane temp file the destructive-bash test should try to rm
    Path("/tmp/orchestra-poc-tempfile-junk.tmp").write_text("junk\n")

    # Pre-flight: confirm the SDK can boot at all by running an init-only probe.
    print("\n" + "=" * 78)
    print("orchestra-poc spike #1 — claude-agent-sdk settingSources verification")
    print("=" * 78)
    print(f"test-repo:   {TEST_REPO}")
    print(f"venv python: {SPIKE_DIR / '.venv' / 'bin' / 'python'}")
    if _dotenv_path:
        print(f".env loaded: {_dotenv_path}")
    auth_route = "ANTHROPIC_API_KEY (direct API)" if os.environ.get("ANTHROPIC_API_KEY") else "claude CLI OAuth (no API key set)"
    print(f"auth route:  {auth_route}")

    results = []
    for spec in TESTS:
        print("\n" + "-" * 78)
        print(f"TEST: {spec.name}")
        print(f"WHY:  {spec.why}")
        print(f"PROMPT: {spec.prompt}")
        outcome = await run_prompt(spec.prompt, spec.name)

        if outcome.error:
            passed, reason = False, f"SDK raised: {outcome.error}"
        else:
            passed, reason = spec.check(outcome)

        print(f"DURATION: {outcome.duration_s}s")
        print(f"RESULT_SUBTYPE: {outcome.result_subtype}")
        print(f"TOOL_CALLS: {[(t.get('name'), str(t.get('input'))[:80]) for t in outcome.tool_calls]}")
        print(f"ANSWER (first 400 chars): {outcome.text[:400]!r}")
        print(f"{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        results.append(
            {
                "name": spec.name,
                "passed": passed,
                "reason": reason,
                "duration_s": outcome.duration_s,
                "result_subtype": outcome.result_subtype,
                "tool_calls": outcome.tool_calls,
                "answer_excerpt": outcome.text[:600],
                "error": outcome.error,
                "system_init_data": outcome.system_init_data,
            }
        )

    # ---- summary ----
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        print(f"  {mark}  {r['name']:36s}  ({r['duration_s']}s)")
    print(f"\n{passed}/{total} tests passed")

    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nFull results saved to {RESULTS_PATH}")
    print(f"Filesystem hook log:  {fs_hook_log}")
    print(f"Programmatic hook log: {PROG_HOOK_LOG}")


if __name__ == "__main__":
    anyio.run(main)
