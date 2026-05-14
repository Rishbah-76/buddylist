# Spike 01 — `claude-agent-sdk.query()` settingSources verification

**Risk it retires:** if the Agent SDK's `query()` with `setting_sources=["user","project"]` doesn't reliably load a teammate's CLAUDE.md, skills, MCPs, and respect read-only `allowed_tools`, the entire cross-developer orchestrator architecture is moot.

## What it does

Runs six independent `query()` calls against `test-repo/` (a synthetic "teammate's repo"). Each call tests one acceptance criterion by checking whether a uniquely-named fingerprint string makes it from the project artifact (CLAUDE.md, rule, skill, MCP server) into the model's answer.

| Test | What it proves |
|---|---|
| `claude_md_loaded` | Project CLAUDE.md is loaded into the spawned agent's context |
| `skills_discovered` | Project skills under `.claude/skills/` are discoverable |
| `mcp_server_started` | `.mcp.json` server boots; its tool is callable; result flows back |
| `path_scoped_rule_loaded` | Path-scoped rule under `.claude/rules/` activates when a `.py` file is read |
| `edit_write_not_in_allowed_tools` | `allowed_tools=["Read","Grep","Glob","Bash"]` blocks Edit/Write |
| `destructive_bash_blocked_by_hook` | Programmatic PreToolUse hook blocks `rm`/`dd`/etc Bash commands |

## How to run

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./run.sh
```

## Outputs

- `results.json` — structured PASS/FAIL with per-test detail
- `spike-prog-hook-log.jsonl` — every event captured by the Python programmatic hooks
- `test-repo/hook-log.jsonl` — every event captured by the filesystem hooks in `.claude/settings.json`

The two hook logs let us cross-check whether each artifact was loaded *and* whether the SDK's hook surface matches what the docs claim.
