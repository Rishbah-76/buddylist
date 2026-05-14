# orchestra-poc — Handoff Note

**Last updated:** 2026-05-14
**Built by:** Rishabh + Claude across 3 sessions (May 12–14, 2026)
**Status:** v0.1 protocol fully working end-to-end with XP browser UI demoed via Playwright. Ready for v0.2 UI polish (the new `/ui-ux-pro-max` skill is for this phase).

> **For the next session:** start by reading `~/.claude/projects/-Users-rishabh-Documents-rishabh-startup-ideas/memory/MEMORY.md` (auto-loaded). All prior decisions and spike results are indexed there. This file is the "what to do next" addendum.

---

## 1. The product, in one paragraph

**orchestra** is a federated layer that lets multiple developers' personal Claude Code sessions talk to each other across laptops. Each dev installs a small local agent (`@orchestra/agent`) that exposes one MCP tool — `ask_teammate(name, question)` — to their interactive Claude Code. When called, the agent routes the question through a shared broker to the named teammate's local agent, which spawns an *ephemeral* Claude SDK `query()` in that teammate's repo (with their full project context — CLAUDE.md, skills, MCPs, code), gets a real answer, and ships it back. The whole interaction is also accessible through a Windows-XP-styled browser team-room where each online teammate is a draggable window. The wedge: BYO-laptop personal-CLI federation is empty in the market — Claude Agent Teams is single-laptop, Devin is cloud-only, Cody is cross-repo retrieval (not session orchestration). Target buyer: small startup teams of 5–20 devs, bottom-up adoption.

---

## 2. What's done (4 spikes + team-room, all green)

### Spike 01 — `claude-agent-sdk.query()` settingSources verification (synthetic)
- **Result:** 6/6 PASS
- Path: `orchestra-poc/spikes/01-sdk-settingsources/`
- Proves: SDK with `setting_sources=["user","project","local"]` reliably loads CLAUDE.md, project skills (.claude/skills/), .mcp.json servers, path-scoped rules; `allowed_tools` denies writes; `PreToolUse` hook blocks destructive Bash.
- **Latency:** 3.9–19s per query (tool-using).

### Spike 02 — same mechanism on Rishabh's REAL repo (`playground-quickInsights`)
- **Result:** 6/6 PASS
- Path: `orchestra-poc/spikes/02-real-repo-query/`
- Proves: same mechanism works on real Claude Code projects (nested CLAUDE.md under `backend/`, real auto-memory at `~/.claude/projects/<slug>/memory/`, real codebase navigation, real `git log`).
- **SHA256 invariance:** `backend/CLAUDE.md` digest `c504d759c1fb7659` identical pre/post — zero bytes modified.
- **SummaryCard extraction:** parses last 2MB of a 32MB session jsonl in under 100ms to surface "what is Bob currently working on" (last 5 user prompts).

### Spike 03 — stub MCP server discovered + invoked via project .mcp.json
- **Result:** 3/3 PASS
- Path: `orchestra-poc/spikes/03-mcp-stub-server/`
- Proves: caller side. SDK Claude (proxying for an interactive Claude Code) finds `mcp__orchestra-agent__ask_teammate` via `.mcp.json` registration, calls it through real MCP protocol, gets a stub reply. Triple-confirmed: SDK tool_call recorded, stub signature tag in answer, stub log file appended.

### Spike 04 — full broker round-trip
- **Result:** PASS first try, all 6 verification signals green
- Path: `orchestra-poc/spikes/04-broker-roundtrip/`
- Proves: end-to-end protocol. Alice's Claude → MCP stdio → Alice's agent → outbound WSS → local broker → Bob's agent → SDK query in real `playground-quickInsights` repo → answer flows back.
- **Latency breakdown:** broker wire = ~2ms, SDK query on real repo = 17.6s, Alice's Claude framing = ~14s, total wall = 31.95s.
- **The answer Bob's spawned Claude produced** correctly identified the 4-pass pipeline (Semantic Read / Structured Facts / Diagnostics / Executive Synthesis on Opus), citing real files `backend/CLAUDE.md` and `backend/playground/core/stages.py`.

### Team-room v0.1 — XP-styled browser UI
- Path: `orchestra-poc/team-room/`
- Stack: Vite + React + xp.css (vendored locally in `public/xp.css`)
- Browser connects directly to broker as `<name>-ui`, peer of the agents
- Each online teammate = a Windows-XP window with chat panel
- Verified end-to-end via Playwright (`verify_ui.py`) — three screenshots saved
- One-command demo: `./start-demo.sh` (boots broker + bob + vite); `./stop-demo.sh` to clean up
- **The brand shot is at `team-room/screenshot-3-answered.png`** — keep this for any pitch / tweet.

---

## 3. File layout (everything you need to know is here)

```
orchestra-poc/
├── HANDOFF.md                             ← this file
├── broker/
│   └── server.py                          ← 80-line WS broker (pure `websockets`)
├── agent/
│   ├── orchestra_agent.py                 ← THE production-bound dual-role agent
│   ├── orchestra_stub_server.py           ← spike-03 stub (kept for reference)
│   ├── stub-call-log.jsonl                ← spike-03 invocation log
│   └── agent-call-log.jsonl               ← live runtime log: every ask/answer with convId+timing
├── spikes/
│   ├── 01-sdk-settingsources/             ← .venv lives here (SHARED by all spikes/team-room/Playwright)
│   │   ├── .venv/                         ← Python 3.14, claude-agent-sdk, mcp, websockets, fastapi, playwright
│   │   ├── spike.py
│   │   ├── test-repo/                     ← synthetic teammate's repo
│   │   ├── FINDINGS.md
│   │   ├── results.json
│   │   └── …
│   ├── 02-real-repo-query/
│   │   ├── spike.py                       ← runs against /Users/rishabh/Desktop/playground-quickInsights
│   │   ├── FINDINGS.md
│   │   └── results.json
│   ├── 03-mcp-stub-server/
│   │   ├── verify.py
│   │   ├── register-user.sh               ← OPTIONAL: wire stub into ~/.claude/settings.json (with backup)
│   │   ├── unregister-user.sh
│   │   ├── FINDINGS.md
│   │   └── test-workspace/.mcp.json
│   └── 04-broker-roundtrip/
│       ├── verify.py                      ← spawns broker + bob + drives SDK alice
│       ├── alice.json                     ← {display, team, broker_url, repo}
│       ├── bob.json                       ← repo = playground-quickInsights
│       ├── alice-workspace/.mcp.json      ← created at run, points to orchestra_agent.py
│       ├── FINDINGS.md
│       └── results.json
└── team-room/                             ← XP browser UI (Vite + React)
    ├── README.md
    ├── start-demo.sh                      ← boots broker + bob + vite, writes .demo-pids
    ├── stop-demo.sh                       ← clean shutdown
    ├── verify_ui.py                       ← Playwright e2e test
    ├── package.json                       ← react ^18.3.1, vite ^5.4.10
    ├── vite.config.js
    ├── index.html                         ← loads /xp.css
    ├── public/xp.css                      ← VENDORED XP.css v0.2.6 (256KB, BSD) — DO NOT use CDN
    ├── src/
    │   ├── main.jsx                       ← React mount
    │   ├── App.jsx                        ← parses ?team= ?name= ?broker=, renders desktop+taskbar
    │   ├── TeammateWindow.jsx             ← one XP window with chat
    │   ├── useBroker.js                   ← WS hook: hello/ask/answer
    │   └── styles.css                     ← taskbar, status dots, chat colors, desktop bg
    ├── logs/                              ← broker.log, bob.log, vite.log (gitignored)
    ├── screenshot-1-empty.png             ← state when bob is online but no chat yet
    ├── screenshot-2-asking.png            ← mid-typing
    └── screenshot-3-answered.png          ← THE BRAND SHOT
```

Workspace root contains:
- `.env` (chmod 600, gitignored — has `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `DEEPINFRA_API_KEY`)
- `.env.example` (committed; key names only, no values)
- `.gitignore` (covers .env, .env.*, .venv, hook logs, build dirs)

Not yet a git repo. Once you `git init`, the .gitignore is correct — no `git rm --cached` cleanup needed.

---

## 4. The architecture diagram, for orienting

```
┌─────────────────────────────────────────────────────────────────────────┐
│   browser (orchestra-poc/team-room/)                                    │
│   Vite + React, XP.css                                                  │
│   one window per teammate, draggable (TODO), chat panel each            │
└────────────┬────────────────────────────────────────────────────────────┘
             │ WS to broker (browser is a peer of agents in the team)
             │
             │
┌────────────▼────────────────────────────────────────────────────────────┐
│   broker  (orchestra-poc/broker/server.py)                              │
│   pure `websockets` lib, 80 lines                                       │
│   routes JSON {hello, ask, answer, error} by teamCode → display         │
│   currently localhost:8765 — port to CF Workers + Durable Objects later │
└────────────▲────────────────────┬───────────────────────────────────────┘
             │ outbound WSS       │ outbound WSS
             │                    │
┌────────────┴───────────────┐    └──────────┐
│  Alice's local agent       │               │
│  --mcp-stdio mode          │   ┌───────────▼────────────────────────┐
│  ↑ MCP stdio to her Claude │   │  Bob's local agent                 │
│    when she asks "ask_     │   │  callee-only (no --mcp-stdio)      │
│    teammate(bob, …)"       │   │  on incoming ask:                  │
│  ↓ relays via broker       │   │    spawn claude_agent_sdk.query()  │
└────────────────────────────┘   │    in cfg["repo"] (read-only,      │
                                  │    safety hooks for destructive    │
                                  │    bash + sensitive read)          │
                                  └─────────────┬──────────────────────┘
                                                ▼
                                  Bob's REAL repo (e.g., playground-quickInsights)
                                  ephemeral Claude reads files, answers
```

**Same `orchestra_agent.py` binary plays both roles** — `--mcp-stdio` flag toggles whether it ALSO runs as a stdio MCP server for the dev's Claude Code. Both modes share the same broker WS.

---

## 5. How to run anything (the dev loop)

orchestra is now a real Python package. After `uv pip install --editable .` you get the `orchestra` CLI:

```
orchestra broker [--tunnel]
orchestra tunnel
orchestra agent  --config X.json
orchestra agent  --team T --as N --broker URL --repo PATH [--mcp-stdio]
```

`agent/orchestra_agent.py` and `broker/server.py` are thin back-compat shims that re-export the new modules, so existing spike scripts and `.mcp.json` registrations keep working.

### Demo (browser UI + bob agent + broker, single machine)
```bash
cd orchestra-poc/team-room
./start-demo.sh    # → http://localhost:5173/?team=spike04-test&name=rishabh
./stop-demo.sh     # clean shutdown
```

`start-demo.sh` now invokes `orchestra broker` and `orchestra agent --config bob.json` under the hood. PIDs land in `team-room/.demo-pids`.

### Cross-laptop demo (free Cloudflare quick tunnel)

`cloudflared` is a one-time install (`brew install cloudflared` / `winget install Cloudflare.cloudflared`). Then:

```bash
# On the host laptop (you):
orchestra broker --tunnel
# → prints a wss://<random-words>.trycloudflare.com/ URL

# On the teammate's laptop (after `uv pip install --editable <orchestra-poc>` or
# `pip install git+...`):
orchestra agent \
  --team   spike04-test \
  --as     alice \
  --broker wss://sandwich-spears-voltage-seeing.trycloudflare.com/ \
  --repo   ~/code/some-microservice
```

The tunnel URL is freshly assigned each run and dies when you Ctrl-C. No CF account, no DNS, no auth — anyone with the URL + team code can join, so treat both as a shared secret. Real auth (GitHub OAuth → team = org) is HANDOFF §7.G.

### Re-run any spike
```bash
orchestra-poc/spikes/01-sdk-settingsources/run.sh
orchestra-poc/spikes/02-real-repo-query/run.sh
orchestra-poc/spikes/03-mcp-stub-server/run.sh
orchestra-poc/spikes/04-broker-roundtrip/run.sh
```

Each run.sh uses `spikes/01-sdk-settingsources/.venv/bin/python` — the SHARED venv. Don't create separate venvs. The packaged CLI (`orchestra`) is installed into this same venv.

### Add Alice as a second teammate on the same laptop
The demo boots just Bob. To add a second teammate locally:
```bash
orchestra-poc/spikes/01-sdk-settingsources/.venv/bin/orchestra agent \
  --config orchestra-poc/spikes/04-broker-roundtrip/alice.json
```
Alice's `repo` in alice.json points to a tiny scratch workspace inside the spike dir — replace with another real repo if you want her to answer real questions. Or skip the config entirely and use the inline flags shown in the cross-laptop section above.

---

## 6. Critical context about the codebase

1. **Auth = .env + python-dotenv.** Every spike script does `load_dotenv(find_dotenv(usecwd=True))` at top to pick up `ANTHROPIC_API_KEY` from workspace root. The SDK auto-prefers API key over the user's `claude` CLI OAuth when both are available. Confirmed working in spikes 1–4.

2. **`.env` security.** Real production keys live in it. Already chmod 600. Already in .gitignore. **NEVER echo the values, NEVER include them in any committed file or chat output.** `.env.example` exists with key names only.

3. **xp.css MUST be served locally** (`public/xp.css`). The CDN version (`https://unpkg.com/xp.css/dist/XP.css`) loads inconsistently in headless Chromium — saw the title-bar gradient fail to apply during the first Playwright run. We vendored 256KB locally to fix it. If you ever switch back to CDN, you'll get a broken-looking demo.

4. **The shared venv is at `spikes/01-sdk-settingsources/.venv/`** and contains: `claude-agent-sdk`, `mcp`, `anyio`, `python-dotenv`, `websockets`, `fastapi`, `uvicorn`, `playwright` (with chromium), `pyjwt`, all transitive deps. Python 3.14.2.

5. **The `claude-agent-sdk` package version is 0.1.81.** API surface used: `query()`, `ClaudeAgentOptions`, `HookMatcher`, `AssistantMessage`, `ResultMessage`, `TextBlock`, `ToolUseBlock`. Hooks defined as async callbacks `async def(input_data, tool_use_id, context) -> dict`.

6. **The protocol is fully proven.** No more research-spike-style work needed for correctness. From here it's pure engineering: cross-machine, real auth, more UI surface, broker hardening.

7. **Demo state right now (2026-05-14):** broker + bob + vite running on this Mac. PIDs in `.demo-pids`. URL: http://localhost:5173/?team=spike04-test&name=rishabh

---

## 7. What's still to build (in priority order)

### A. UI polish — v0.2 of the team-room (THIS IS WHERE `/ui-ux-pro-max` SKILL APPLIES)

**Highest user-facing impact. Use the new skill heavily here.**

| Task | Why it matters | Rough scope |
|---|---|---|
| **Draggable windows** | XP feels broken if windows are pinned. Use `react-rnd` or `react-draggable`. Persist last position to localStorage so layout is sticky | ~half day, isolated change to TeammateWindow.jsx |
| **Window minimize / maximize / close actions** | The chrome buttons are decorative now — wire them. Minimize tucks to taskbar; close removes from desktop until teammate sends a new message | ~half day |
| **Live notification balloons** | When a teammate connects/disconnects mid-session, show an XP-style balloon ("Bob is online") for 3s in bottom-right above taskbar. Same for incoming messages from teammates with closed windows | ~half day |
| **Network Neighborhood desktop icon** | A draggable XP icon on the desktop labeled "My Network Places". Double-click opens a window listing all teammates' service contracts (a future SummaryCard surface). For v0.2: just lists connected teammates with last-seen | ~1 day |
| **Start menu** | Click the green start button to open an XP-style start menu with: My Documents (team ADRs), My Computer (settings), Programs (placeholder for future tools), Log Off (disconnect from team), Turn Off Computer (exit) | ~1 day |
| **Status indicators with real semantics** | Currently green=online, orange=busy, grey=offline. Add: yellow=stale-card (offline >5min, can fall back to async card), red=error | ~few hours |
| **Conversation persistence** | Right now chat is lost on page refresh. Save per-teammate convo to localStorage; restore on mount | ~few hours |
| **Markdown rendering in answers** | Bob's answers come back with markdown (bold, code, lists). Currently rendered as plain text with whitespace-pre-wrap. Add `marked` or `react-markdown` for proper rendering — file paths should be clickable, code blocks should have syntax highlighting | ~few hours |
| **Auto-reconnect to broker** | If the WS drops (e.g., broker restart), reconnect with exponential backoff. Currently `useBroker.js` just sets status to "closed" and gives up | ~few hours |
| **Better empty / loading states** | When connecting, show an XP-style hourglass cursor + "Connecting…" dialog. When 0 teammates, the desktop hint is plain text — make it a proper XP info box | ~half day |
| **Mobile / responsive ditching** | This is a desktop-only experience. Add a "best on desktop" notice for narrow viewports — don't try to make it work on phones | ~30 min |
| **Sound effects (optional, very on-brand)** | XP startup sound on page load; ding when teammate replies; Windows error chime when broker drops. Off by default with a 🔊 toggle in taskbar tray | ~half day |

### B. Protocol — Spike 05: recursion guard (last protocol risk)

Bob's spawned ephemeral Claude has the orchestra MCP server in its tools list (because `setting_sources=["user","project"]` loads it). It could theoretically call `ask_teammate("alice", …)` and create a loop.

**Fix options:**
1. Add a `convId` chain in env (`ORCHESTRA_CONV_CHAIN=conv1,conv2,...`); the agent refuses if the requested teammate is already in the chain.
2. When spawning the ephemeral query, override `allowed_tools` to exclude `mcp__orchestra-agent__ask_teammate` entirely. Simpler, more brittle (loses the ability to do legitimate multi-hop queries).
3. Disable orchestra MCP server in spawned queries via `mcp_servers: []` parameter.

**Recommended:** option 1 — preserves multi-hop while preventing loops. ~20 minutes.

Path: create `orchestra-poc/spikes/05-recursion-guard/`. Test: have alice ask bob to ask alice — verify the second hop is refused.

### C. Real cross-laptop test (Spike 06)

Same code, two physical machines. Need:
1. A public broker URL — easiest path is **Cloudflare Tunnel** (`cloudflared tunnel --url http://localhost:8765`) which gives you a free wss URL in 30 seconds without any deployment.
2. A second machine (your friend / second laptop / a remote SSH session into a Linux box).
3. Both machines run the agent with the same `teamCode` and the same broker URL.

Most likely issues to watch for:
- WS clean-close on connection loss
- DNS / TLS certs (CF Tunnel handles this)
- Latency profile over real internet (vs. ~2ms localhost)

### D. Production broker port to Cloudflare Workers + Durable Objects

Wire protocol stays identical. CF Workers gives:
- Free tier handles thousands of teams
- Each `teamCode` → one Durable Object (perfect WS fan-out primitive)
- Zero ops

Files to write:
- `broker-cf/wrangler.toml`
- `broker-cf/src/index.ts` — DO with `webSocketMessage()` handler that mirrors `server.py` routing logic

### E. SummaryCard auto-publish + offline fallback

Spike 02 already proved the extraction works. Now wire it into the agent:
- Every ~10 min (or on `git commit` via filesystem hook), each agent re-extracts + pushes its summary card to the broker.
- Broker stores cards (D1 / SQLite).
- When dev A asks a teammate who's offline, broker auto-answers from the card with `"⚠️ Bob is offline. Best-effort answer from his card 2h ago: ..."`.

This is the **async layer** that gives the product value when teammates aren't online.

### F. Multi-team support / team switching in UI

Currently `?team=` is hardcoded into the URL. Add:
- A "switch team" item in start menu
- Multiple teamCodes saved in localStorage
- Optional: "create new team" generates a random teamCode you can share

### G. Real auth (eventually, for B2B)

GitHub OAuth → team = GitHub org. Replaces `teamCode`-as-shared-secret. Only needed once you have 3+ paying teams or any enterprise interest. Not before.

---

## 8. Known issues / technical debt

| Issue | Severity | Notes |
|---|---|---|
| `xp.css` v0.2.6 is the ONLY tested version. v0.5.0 doesn't exist on npm; newer versions may break selectors | medium | Pinned in `public/xp.css` |
| `start-demo.sh` hardcodes Bob's repo path (`/Users/rishabh/Desktop/playground-quickInsights`) via `bob.json`. Won't work on other machines | medium | Make `bob.json` configurable via env var or copy to dot-config |
| Vite dev server doesn't have hot reload working perfectly with the WS connection — sometimes a connection dies on refresh and React reconnects. Not a real bug, just feels janky | low | Will fix itself with auto-reconnect (item A above) |
| `verify_ui.py` keyword check is loose ("goldstar", "pipeline", "thout") — could pass on hallucination if model knew Thout from training | low | For real verification, the answer cites file paths that the model couldn't fabricate |
| Spike-04's `verify.py` hangs ~30 seconds at teardown because Vite's child node process doesn't always die cleanly on SIGTERM | low | Use a process group kill instead |
| No tests outside the spike verifies; no CI | medium | Fine for POC; needed before shipping |
| Auto-memory storage (`~/.claude/projects/<slug>/memory/`) is not federated. If a teammate's auto-memory contains a relevant fact, only their machine has it. The orchestrator only pulls in CLAUDE.md / skills / .mcp.json today | strategic | Could be the SummaryCard's job to extract auto-memory headlines |
| Demo currently shows `<name>-ui` is the browser identifier. If you connect both Claude Code AND the browser as "rishabh", they collide in the broker — broker accepts both but the second one overwrites the WS in the registry. Display name uniqueness should be enforced | medium | Easy fix in broker `handler()` |

---

## 9. Things explicitly NOT done (don't accidentally re-do them)

- **Cloudflare deployment** — local broker only. Don't port to CF until cross-laptop is validated locally with two laptops + cloudflared tunnel.
- **Forking daedalOS** — we considered, then built minimal from scratch with xp.css. ~200 lines vs. fork-and-customize a 100kloc Next.js codebase. Don't switch back unless v0.2 hits a wall.
- **Recursion guard** (Spike 05) — deferred but trivial; do it before any second-laptop demo.
- **GitHub OAuth** — deferred until 3+ paying teams or enterprise interest.
- **TypeScript** — team-room is plain JS. Vite handles JSX. Don't add TS unless you're going to maintain the project for years.

---

## 10. What the new `/ui-ux-pro-max` skill is for (my read)

The user installed it after the team-room v0.1 ship. Logical inference: they want serious UI/UX polish on the next pass. The skill should be invoked when:

- They ask for any visual / interaction improvements to the team-room
- They want a redesign / mockup / brand exploration
- They ask "make it look better" / "more polished"
- Any work in `orchestra-poc/team-room/src/` or `public/`

Don't invoke it for:
- Backend / agent / broker work
- Spike additions
- Memory / docs / handoff work

The brand identity is **non-negotiable Windows XP**. Bliss desktop, blue title bars, Tahoma font. Polish should respect this — no flat design, no glass morphism, no gradient overhauls toward modern aesthetics. The whole product moat depends on the XP novelty.

---

## 11. Memory pointers for the next session

After restart, the next session will auto-load:
- `~/.claude/projects/-Users-rishabh-Documents-rishabh-startup-ideas/memory/MEMORY.md` (index)
- It links to: user_role, project_session_orchestra_idea, research_session_orchestra_landscape, project_session_orchestra_architecture(_v2), project_session_orchestra_poc_plan, project_orchestra_auth, research_claude_code_state_inventory, spike01_results, spike02_results, spike03_results, spike04_results, team_room_v01

**The next session should:**
1. Read MEMORY.md (auto-loaded)
2. Read this HANDOFF.md (point them at it: `Read /Users/rishabh/Documents/rishabh_startup_ideas/orchestra-poc/HANDOFF.md`)
3. Confirm `/ui-ux-pro-max` skill is now in available-skills list
4. Ask Rishabh what he wants to tackle from section 7's priority list — or wait for direction

---

## 12. The screenshot to keep handy

`orchestra-poc/team-room/screenshot-3-answered.png` — the brand shot. Real Windows XP window, real teammate name, real answer with real file path citation. This is the artifact for any pitch deck / demo / tweet / VC convo.

---

*End of handoff.*
