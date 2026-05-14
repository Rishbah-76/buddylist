# Spike 03 — Findings

**Run date:** 2026-05-12  •  **Result: 3/3 PASS, first try — risk #2 retired**

The dev's interactive Claude (proxied here by an SDK `query()` with the same `settingSources` mechanism the CLI uses) discovers and invokes the orchestra-agent stub via real MCP protocol. Combined with spikes 01/02, **both halves of the orchestrator protocol are now proven end-to-end.**

## Tests

| Test | Latency | What it proves |
|---|---|---|
| **T1 — standalone sanity** | 0.23s | Stub server boots and speaks MCP. Real `mcp.client.stdio` connected, called `initialize` + `tools/list`, got back `['ask_teammate']` |
| **T2 — SDK discovery** | 6.4s | `.mcp.json` registration path works. Model identified the tool as `mcp__orchestra-agent__ask_teammate` and even called out the `mcp__<server>__<tool>` naming convention |
| **T3 — SDK end-to-end** | 11.0s | Full round-trip: model called the tool, stub's signature tag appeared verbatim in the answer, and the stub's log file gained the exact entry with caller args |

## The signal that matters

T3 returned this in `tool_calls`:
```
mcp__orchestra-agent__ask_teammate({'name': 'bob', 'question': 'what auth scheme does your /orders POST endpoint use?'})
```

And the stub log got:
```json
{"tool": "ask_teammate", "teammate": "bob",
 "question": "what auth scheme does your /orders POST endpoint use?",
 "iso": "2026-05-12T11:55:34Z"}
```

These three facts (SDK saw the call, model's answer carried the stub tag, log file recorded the invocation) together prove the call wasn't hallucinated — a real subprocess ran on this Mac and produced the reply Claude relayed.

## What both halves now look like

```
┌──────────────────────────────────────────────────────────────────────┐
│   PROVEN — spike 03                                                  │
│  ┌─────────────────────┐    MCP stdio    ┌───────────────────────┐   │
│  │ Dev A's interactive │ ──────────────► │ orchestra-agent stub  │   │
│  │ Claude Code         │ ◄────────────── │  (the hot wire)       │   │
│  └─────────────────────┘   ask_teammate  └──────────┬────────────┘   │
└──────────────────────────────────────────────────────┼───────────────┘
                                                       │
                                                       │ (broker — next, spike 04)
                                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│   PROVEN — spike 01/02                                               │
│  ┌──────────────────────────┐               ┌────────────────────┐   │
│  │ Dev B's local agent      │ ──── SDK ────►│ ephemeral Claude    │   │
│  │ (receives ask, spawns    │   query()     │ in Bob's real repo, │   │
│  │  query() in Bob's repo)  │ ◄────────────│ read-only, real     │   │
│  └──────────────────────────┘   answer      │ project state       │   │
│                                              └────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

The broker that connects the two halves is a thin WebSocket router. No more Anthropic-API risk; only networking risk.

## Side artifacts produced

- **`orchestra-poc/agent/orchestra_stub_server.py`** — 90 lines, single-tool MCP stdio server. Future home of the real `ask_teammate` that calls the broker. The "hot wire" stays; only the call_tool body changes.
- **`orchestra-poc/agent/stub-call-log.jsonl`** — every invocation logged with caller args. Future versions log call timing + broker round-trip latency.
- **`register-user.sh` / `unregister-user.sh`** — optional scripts to wire the stub into `~/.claude/settings.json` with backup safety. Lets you `/mcp` the tool in any Claude Code session yourself.

## What's now ahead

| Risk | Status |
|---|---|
| 1. SDK loads teammate's project state | ✅ Spike 01 (synthetic) + 02 (real repo) |
| 2. Interactive Claude can find + call our MCP tool | ✅ Spike 03 |
| 3. **Two-process WSS round-trip via broker** | ⏳ Next |
| 4. Recursion guard (spawned Claude can't `ask_teammate` back into asker) | After #3 |

Spike 04 is where it gets fun: we replace the stub's hardcoded reply with a call to a Cloudflare Workers + Durable Objects broker, plus a second instance of the local agent running with the same `teamCode`. Two laptops are simulated on this one Mac for now; real cross-laptop validation comes later. After spike 04, we have a working v0.1 protocol.
