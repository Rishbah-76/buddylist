# orchestra team-room — XP-style browser UI

A Vite + React single-page app that lets you talk to your teammates' Claudes through the orchestra broker, styled like a Windows XP desktop. Each online teammate is a draggable window with its own chat panel.

This UI is a **direct client of the broker** — it does not go through Claude Code on your machine. Open the URL, type a question into a teammate's window, and the broker routes it to their local agent, which spawns an ephemeral Claude in their repo and streams the answer back.

## Quick start (one command)

```bash
./start-demo.sh
# → http://localhost:5173/?team=spike04-test&name=rishabh-ui
```

That single command boots:
- the broker on `ws://localhost:8765/`
- Bob's agent connected to the broker, with `repo = ~/Desktop/playground-quickInsights`
- the Vite dev server on `http://localhost:5173/`

PIDs are written to `.demo-pids`. Stop with:

```bash
./stop-demo.sh
```

Logs go to `logs/`.

## URL parameters

```
http://localhost:5173/?team=<teamCode>&name=<yourDisplayName>&broker=<wsUrl>
```

| param   | default                      | meaning |
|---------|------------------------------|---------|
| `team`  | `spike04-test`               | join this team room (== broker's Durable Object key in production) |
| `name`  | `guest-ui`                   | how you appear to other teammates |
| `broker`| `ws://localhost:8765/`       | broker WebSocket URL — change for staging/prod |

## What you see

- A Windows XP desktop (Bliss-style gradient background, blue taskbar)
- One **xp-style window** per online teammate with:
  - title bar: green status dot + teammate name (turns orange and pulses while their Claude is thinking)
  - chat log: your messages (blue) and teammate replies (beige), with auto-scroll
  - input + Send button
- A taskbar showing your team, name, broker status, and online teammate count

## Architecture

```
browser ──── ws ────► broker ──── ws ────► teammate's local agent
                                              │
                                              ▼
                            spawned ephemeral Claude in their repo
                            (read-only, with safety hooks)
```

The browser sends a `hello` on connect (declaring `team` + `display`), then sends `ask` messages and listens for `answer` messages. Same wire protocol as the agents — the broker doesn't care who's a human and who's a CLI.

## Files

```
team-room/
├── index.html               # entry; loads xp.css from public/
├── package.json             # vite + react
├── vite.config.js
├── src/
│   ├── main.jsx             # React mount
│   ├── App.jsx              # top-level: parse URL, render windows, taskbar
│   ├── TeammateWindow.jsx   # one XP window with chat
│   ├── useBroker.js         # WS hook: hello, conversations, busy state, ask()
│   └── styles.css           # overrides + taskbar + desktop background
├── public/
│   └── xp.css               # vendored from unpkg (256KB, BSD)
├── verify_ui.py             # Playwright headless end-to-end test
├── start-demo.sh
├── stop-demo.sh
└── logs/                    # broker.log, bob.log, vite.log
```

## End-to-end test

```bash
./start-demo.sh
.venv/bin/python verify_ui.py   # uses the spike-01 venv
```

The test opens the page in headless Chromium, types a real question, waits for the answer, and saves three screenshots (`screenshot-1-empty.png`, `screenshot-2-asking.png`, `screenshot-3-answered.png`).
