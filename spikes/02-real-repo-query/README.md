# Spike 02 — SDK query against a REAL teammate's repo

**Risk it retires:** spike #1 proved the SDK loads a *synthetic* test-repo's CLAUDE.md / skills / MCPs. This spike confirms the same mechanism works on **real-world Claude Code projects** — nested CLAUDE.md (under `backend/`), real auto-memory, real codebase navigation — without modifying a single byte of the target repo.

**Target repo:** `/Users/rishabh/Desktop/playground-quickInsights/` (Rishabh's active Thout AI playground).

## What it does

| Phase | What it does |
|---|---|
| 1. **SummaryCard preview** | Reads the latest session `.jsonl` from `~/.claude/projects/-Users-rishabh-Desktop-playground-quickInsights/`, extracts metadata + last 5 user prompts. This is exactly what the orchestrator broker would surface to a teammate as "what Bob is currently working on" |
| 2. **Integrity baseline** | SHA256 of key files (`backend/CLAUDE.md`, memory index, `.claude` artifacts) |
| 3. **Six realistic tests** | Project summary from CLAUDE.md, auto-memory loaded, 4-pass pipeline navigation, recent git log, Edit blocked, destructive Bash blocked |
| 4. **Integrity verification** | SHA256 of those same files — **must match Phase 2** |

## Safety guarantees

- `allowed_tools = ["Read","Grep","Glob","Bash"]` — no Edit/Write/NotebookEdit
- `PreToolUse` hook blocks Bash on `rm`, `dd`, `git push`, `git reset --hard`, redirection (`>`), `sudo`
- `PreToolUse` hook blocks Read of `.env` and `~/.claude/.credentials.json`
- Integrity is verified by SHA256 of key files before/after the run

## How to run

```bash
./run.sh
```

(Uses spike 01's venv — no extra install needed.)
