# Spike 03 — stub MCP server, caller-side verification

**Risk it retires:** spikes 01/02 proved we can spawn an ephemeral Claude on a teammate's machine and ask it questions (the *callee* side). This spike proves the *caller* side: the dev's interactive Claude Code can discover and invoke the orchestra-agent's `ask_teammate` tool via real MCP protocol.

## What it builds

- `orchestra-poc/agent/orchestra_stub_server.py` — 30-line stdio MCP server exposing one tool: `ask_teammate(name, question)`. Returns a hardcoded reply tagged `ORCHESTRA-STUB-REPLY-v0` and appends every call to `stub-call-log.jsonl`.
- `test-workspace/` — a scratch project dir with `.mcp.json` registering the stub server at project scope. Created by `verify.py` at the start of each run.

## Three independent tests

| Test | What it proves |
|---|---|
| **T1 — standalone sanity** | Spawn the stub directly via the real `mcp.client.stdio` and confirm it lists `ask_teammate`. Proves the server boots and speaks MCP |
| **T2 — SDK discovery** | SDK `query()` with `cwd=test-workspace, settingSources=["project"]`. Ask Claude to list its MCP tools — `ask_teammate` must appear. Proves `.mcp.json` registration works |
| **T3 — SDK end-to-end** | Same setup, ask Claude to call `ask_teammate("bob", "...")`. Verify: (a) the SDK tool call happened, (b) the stub's signature tag reaches the model's answer, (c) the stub's log file has a new entry. Three-way confirmation that there's no hallucination |

## How to run (automated)

```bash
./run.sh   # uses spike 01's venv; no extra install
```

## How to feel it interactively (optional)

If you want to see the orchestra tool show up in your *own* Claude Code session:

```bash
./register-user.sh     # backs up ~/.claude/settings.json + adds orchestra-agent
# … open Claude Code anywhere, type /mcp to see it, or just ask Claude to use the ask_teammate tool …
./unregister-user.sh   # clean removal (also backs up first)
```

Both scripts back up `~/.claude/settings.json` before touching it. The backups land in `~/.claude/settings.json.bak.<timestamp>` — keep the most recent one until you're sure things still work.

## Outputs

- `results.json` — structured pass/fail for the 3 tests
- `spike-prog-hook-log.jsonl` — every tool call observed by the SDK programmatic hooks
- `../../agent/stub-call-log.jsonl` — every time `ask_teammate` was invoked, with caller args
