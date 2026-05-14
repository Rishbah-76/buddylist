# Spike 04 — Findings

**Run date:** 2026-05-12  •  **Result: PASS on first run (all 6 verification signals green)**

The full orchestrator protocol works end-to-end. Alice's Claude (proxied by the SDK) calls `ask_teammate("bob", …)` → MCP stdio to Alice's local agent → outbound WSS to the local broker → routed to Bob's local agent → spawns SDK `query()` in Bob's REAL `playground-quickInsights` repo → real Claude answers from real CLAUDE.md + real code → reply flows back through broker → Alice's Claude relays it to the user.

## The actual response Bob's Claude produced

> The four LLM passes in the Thout pipeline (per `backend/CLAUDE.md` and `backend/playground/core/stages.py`):
> 1. **Pass 1 — Semantic Read**: chronological narrative (opening, threads, tension w/ intensity, evidence reviewed, direction, closing).
> 2. **Pass 2 — Structured Facts**: bilateral decisions, confirmed actions, proposed actions, forward-looking risks.
> 3. **Pass 3 — Diagnostics**: open questions, misalignments, unknowns, frame check, inferred priorities.
> 4. **Pass 4 — Executive Synthesis (Opus)**: analytical TLDR, traceable bullets, TLDR, confidence level — always run on Opus via the synthesis client.
> (Classification runs upstream as a seeding step but isn't counted as one of the four passes.)

That's not paraphrase, not memorized, not hallucinated — Bob's spawned Claude **opened two files** in the real repo (`backend/CLAUDE.md` and `backend/playground/core/stages.py`) to answer. Even noted "always run on Opus via the synthesis client", which is implementation detail that lives only in the code.

## Six-signal verification (all green)

| Signal | What it confirms |
|---|---|
| ✅ `alice_sdk_called_ask_teammate` | The SDK proxying as Alice's Claude actually called the orchestra MCP tool (not a hallucinated answer) |
| ✅ `broker_routed_both_directions` | Broker log shows both `route ask … : alice -> bob` and `route answer … : bob -> alice` |
| ✅ `bob_received_ask` | Bob's agent log has `incoming_ask` event with the verbatim question |
| ✅ `bob_sent_answer` | Bob's agent log has `outgoing_answer` event with the 709-char reply |
| ✅ `answer_references_real_bob_repo_content` | Answer contains "semantic", "structured", "diagnostic", "synthesis" — all terms from `backend/CLAUDE.md` |
| ✅ `no_sdk_error` | SDK exited cleanly with no exceptions |

## Latency breakdown (broker is essentially free)

From `agent-call-log.jsonl` precise timestamps:

```
12:00:47.477  Alice's MCP server receives ask_teammate(...)
12:00:47.479  Bob's agent receives incoming_ask via broker     ← ~2ms on the wire
12:01:05.077  Bob's agent sends outgoing_answer (709 chars)   ← 17.6s spent in SDK
12:01:05.079  Alice's MCP returns answer to her Claude
```

- **Broker round-trip on the wire: ~2 ms** — the broker is not the bottleneck. Cloudflare Workers porting later won't change the latency story.
- **SDK query() on Bob's real repo: 17.6 s** — included reading two real files (`backend/CLAUDE.md` and `backend/playground/core/stages.py`) + synthesis. Simpler questions ("status check?") should round-trip in 5–10s.
- **Wall total: 31.95 s** — Alice's own Claude added ~14s framing the question, doing deferred-tool lookup, and formatting the relayed answer.

## What this proves about the architecture

1. **The dual-role agent design works.** Single binary plays both caller (MCP stdio) and callee (SDK query) by running both loops concurrently over one shared broker WS. No state divergence, no races observed.
2. **Read-only safety preserved across the network.** Bob's SDK query ran with `allowed_tools=["Read","Grep","Glob","Bash"]` and a destructive-Bash hook. Nothing in his repo was modified.
3. **The shared `teamCode` auth model is sufficient for POC.** Two agents joining `spike04-test` immediately discovered each other in the broker's team registry. No OAuth, no accounts.
4. **Latency profile is acceptable.** The dominating cost is the SDK reading real files — exactly where the value comes from. The orchestrator's overhead is negligible.

## What's still ahead

| Risk | Status |
|---|---|
| 1. SDK loads teammate's project state | ✅ Spike 01 + 02 |
| 2. Interactive Claude finds + invokes our MCP tool | ✅ Spike 03 |
| 3. Two-process broker round-trip with real-repo answer | ✅ Spike 04 |
| 4. Recursion guard (Bob's spawned Claude can't `ask_teammate` back) | ⏳ Spike 05 |
| 5. Real cross-laptop test (not just two processes on this Mac) | ⏳ Spike 06 |
| 6. CF Workers + Durable Objects port of broker | ⏳ Eng |
| 7. SummaryCard auto-publish + offline-fallback | ⏳ Eng |
| 8. XP team-room (fork daedalOS) | ⏳ Eng |

## Files produced this spike (all production-bound)

- `orchestra-poc/broker/server.py` — 80-line local WS broker, ready to port to CF Workers (same wire protocol)
- `orchestra-poc/agent/orchestra_agent.py` — dual-role agent (MCP stdio + WSS) — this IS the local agent that ships with v0.1
- `orchestra-poc/agent/agent-call-log.jsonl` — runtime audit trail (every ask/answer logged with timing + convId)
- `orchestra-poc/spikes/04-broker-roundtrip/{alice,bob}.json` — config schema for the local agent

The protocol is no longer a research question. From here it's engineering.
