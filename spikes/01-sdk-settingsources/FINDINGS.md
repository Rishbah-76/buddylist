# Spike 01 — Findings

**Run date:** 2026-05-12  •  **Result: 6/6 PASS — risk #1 retired**

The Agent SDK's `query()` with `setting_sources=["user","project","local"]` reliably loads everything a teammate's interactive Claude Code session would have. The cross-developer orchestrator architecture is technically feasible on the foundations Anthropic ships today.

## What passed and what it proves

| Test | Latency | What it proves for the product |
|---|---|---|
| `claude_md_loaded` | 3.92s | A spawned ephemeral Claude on Bob's machine automatically gets Bob's `CLAUDE.md` — no manual context injection needed |
| `skills_discovered` | 6.06s | Bob's user-invocable skills under `.claude/skills/` are auto-listed — teammates can ask "use Bob's `/order-contract` skill" |
| `mcp_server_started` | 9.07s | Bob's `.mcp.json` boots the configured stdio server *for the spawned ephemeral session*, and its tools flow back end-to-end |
| `path_scoped_rule_loaded` | 8.26s | Path-scoped rules in `.claude/rules/` load on demand when the spawned Claude reads files matching the glob |
| `edit_write_not_in_allowed_tools` | 19.74s | `allowed_tools=["Read","Grep","Glob","Bash"]` + `permission_mode=default` denies write tools in headless mode; **file confirmed unmodified after 2 Edit attempts** |
| `destructive_bash_blocked_by_hook` | 7.82s | Programmatic `PreToolUse` hook intercepts and blocks `rm`/`dd`/etc Bash commands; model receives the block reason and acknowledges in its answer |

## Hook firing audit

- **22 programmatic hook events** captured across the 6 tests (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop` — all fired)
- **36 filesystem hook events** captured (same events plus `SessionStart` and **`InstructionsLoaded` fired 14 times** — once per CLAUDE.md / rule / skill / config file loaded)
- **Both surfaces fire simultaneously and consistently.** Filesystem hooks (shell commands in `.claude/settings.json`) and programmatic hooks (Python callbacks passed to `query()`) coexist without conflict. The orchestrator can use either or both.

## Bonus findings (positive surprises)

1. **`InstructionsLoaded` is a forensic gold mine.** Each session emits one event per loaded artifact. The orchestrator can use this to: (a) log exactly what context each spawned query received, (b) audit for privacy (was a sensitive file loaded?), (c) tune what to expose per teammate.
2. **`permission_mode: "default"` is a second line of defense.** Even if a tool is somehow in scope but not in `allowed_tools`, the default permission_mode requires interactive approval — which fails closed in headless mode. So write protection has belt + suspenders.
3. **No `ANTHROPIC_API_KEY` needed.** SDK shells out to the user's installed `claude` CLI (v2.1.104) and inherits its OAuth. Every dev who can run Claude Code can run our local agent.
4. **The model uses `ToolSearch` for unknown tools.** When asked to call `mock_get_status`, Claude first called the built-in `ToolSearch` to find it. This is the SDK's "deferred tools" system — has implications for how we expose `ask_teammate` and other orchestra tools.
5. **Latency budget validated.** Tool-using queries: 8–20s. "Ask Bob's Claude about /orders" round trips through broker → SDK query → broker → A will plausibly land at 10–15s. Within the <20s ceiling we set for usable UX.

## What this means for the orchestrator architecture

The pivot from v1 ("write into teammate's running session inbox") to v2 ("spawn ephemeral SDK query() in teammate's repo dir") is correct and works. The whole protocol can be built on:

1. The SDK's `query()` with `setting_sources=["user","project"]` (proven here)
2. The SDK's programmatic hooks for cross-cutting concerns (audit log, blocking, etc.)
3. The filesystem `.claude/settings.json` hooks for things the user already has wired up
4. An MCP server exposing `ask_teammate(name, q)` to the interactive Claude (the dev's actual session)

None of these require any unreleased / unsupported Anthropic primitives.

## Things still to validate before building the broker

The next risks, in order:

1. **Bidirectional MCP servers in the broker direction.** Our local agent needs to expose `ask_teammate` as an MCP tool to the dev's *interactive* Claude Code. That means a `.mcp.json` entry pointing at our agent binary. Spike: register a trivial MCP server with one tool in user-level `~/.claude/settings.json` or per-project `.mcp.json` and confirm Claude Code picks it up. (~30 min)
2. **WSS round trip from local-agent → broker → local-agent.** Spawn two local agents on this Mac with the same `teamCode`, route a message A→broker→B, get a reply. (~2-3 hours including Cloudflare Workers setup)
3. **Recursion guard.** When Bob's spawned SDK query also has the orchestra MCP loaded, prevent it from calling `ask_teammate` back into Alice. Solve with a `convId` chain or per-session tool disablement.
