# Spike 04 — broker round-trip (local, no Cloudflare)

**Risk it retires:** spikes 01/02 proved the *callee* side; spike 03 proved the *caller* side. This spike connects the two halves through a real local WebSocket broker — proving the full protocol A→broker→B→SDK-query-on-real-repo→broker→A actually works end-to-end.

## Architecture

```
verify.py (driver)
   │
   │ SDK query()
   ▼
Alice's Claude (cwd = alice-workspace/, sees .mcp.json)
   │
   │ MCP stdio
   ▼
Alice's orchestra-agent  ──── outbound WSS ───┐
                                              ▼
                                  ┌──── ws://localhost:8765/ ────┐
                                  │   local broker (server.py)   │
                                  └──────────────┬────────────────┘
                                                 ▲ outbound WSS
                                                 │
                                 Bob's orchestra-agent
                                                 │
                                                 │ SDK query()
                                                 ▼
                              Bob's REAL repo: playground-quickInsights
                              (read-only, with safety hooks)
```

## What the test does

`verify.py`:
1. Starts the broker as a subprocess
2. Starts Bob's agent as a subprocess (callee-only, no MCP stdio); waits for its `connected` log line
3. Drives a real Claude via SDK `query()` with `cwd=alice-workspace`. The `.mcp.json` there spawns Alice's agent on demand
4. Alice's Claude is asked to call `ask_teammate("bob", "what are the four passes of the LLM pipeline?")`
5. The call flows: Alice's agent → broker → Bob's agent → ephemeral SDK query in `playground-quickInsights` → answer back
6. **6-signal verification:**
   - SDK actually invoked the MCP tool
   - Broker log shows both `route ask` and `route answer` lines
   - Bob's agent log shows `incoming_ask` event
   - Bob's agent log shows `outgoing_answer` event
   - Final answer mentions terms only present in Bob's REAL repo's CLAUDE.md (`semantic` / `structured` / `diagnostic` / `synthesis` or `pass 1..4`)
   - No SDK error

If all six pass, the orchestrator protocol works end-to-end.

## Run

```bash
./run.sh
```

Outputs `broker.log`, `bob.log`, the SDK invocation transcript, and `results.json`. Each subprocess is cleanly stopped after the test (whether it passes or fails).

## What's deliberately NOT in this spike

- Cloudflare Workers deployment (kept local — port it to CF after the protocol is proven)
- Multiple teams (single shared `teamCode = "spike04-test"`)
- Recursion guard (Alice's spawned ephemeral Claude in Bob's repo *could* technically call `ask_teammate` itself — fix in spike 05)
- Auth beyond the shared teamCode
- E2E encryption
- Reconnect logic if the broker drops a WS
