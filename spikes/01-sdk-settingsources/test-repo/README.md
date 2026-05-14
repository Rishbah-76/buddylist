# test-repo (Bob's orders service)

This is a synthetic "teammate's repo" used by the orchestra-poc SDK spike to verify that an `Agent SDK query()` invoked from outside picks up the full Claude Code project setup. Nothing here is real production code.

The repo contains exactly the artifacts the orchestrator needs to federate across laptops:

| File / dir | Tests |
|---|---|
| `CLAUDE.md` | Project instructions are loaded (contains a unique fingerprint string) |
| `.claude/rules/python-style.md` | Path-scoped rule for `*.py` files (also fingerprinted) |
| `.claude/skills/order-contract/SKILL.md` | A user-invocable skill is discoverable (fingerprinted) |
| `.mcp.json` + `mock_mcp_server.py` | A project-level MCP server is auto-started, its tool callable (fingerprinted) |
| `orders_service.py`, `users_service.py` | The actual "service code" the spawned Claude reads |
| `.claude/settings.json` + `.claude/hooks/log_hook.sh` | Every lifecycle hook is wired to append the event JSON to `hook-log.jsonl`, giving an audit trail of what loaded and when |
