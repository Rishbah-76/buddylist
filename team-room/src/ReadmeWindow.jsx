/**
 * ReadmeWindow — the "Read Me / Welcome" XP window shown to first-time users.
 * Static content, draggable, position persisted to localStorage. Opens via the
 * "Read Me" desktop icon and auto-opens the first time the page is loaded.
 */

import { useEffect, useRef, useState } from "react";
import { Rnd } from "react-rnd";
import ReactMarkdown from "react-markdown";

const LS_GEOMETRY = "orchestra:readme:geometry";
const DEFAULT_POS = { x: 320, y: 60 };
const DEFAULT_SIZE = { w: 560, h: 460 };

function loadGeom() {
  try {
    const raw = localStorage.getItem(LS_GEOMETRY);
    if (!raw) return { pos: DEFAULT_POS, size: DEFAULT_SIZE };
    const parsed = JSON.parse(raw);
    return {
      pos: parsed.pos || DEFAULT_POS,
      size: parsed.size || DEFAULT_SIZE,
    };
  } catch {
    return { pos: DEFAULT_POS, size: DEFAULT_SIZE };
  }
}

function saveGeom(geom) {
  try {
    localStorage.setItem(LS_GEOMETRY, JSON.stringify(geom));
  } catch {
    /* ignore */
  }
}

const README_MD = `
# Welcome to your Orchestra team-room

## What is this?
Orchestra federates **Claude Code sessions** across laptops. Every teammate runs the same \`orchestra\` CLI on their own machine, and the icons on this desktop are their live agents.

Ask any teammate a question and **their** Claude reads **their** repo, drafts an answer, and ships it back — without you ever needing access to their code.

## How it works

\`\`\`
   browser (this window) ──ws──► broker ──ws──► teammate's local agent
                                                     │
                                                     ▼
                                       ephemeral Claude in their repo
                                       (read-only, with safety hooks)
\`\`\`

1. Every dev runs \`orchestra agent --team T --as NAME --broker WSS --repo PATH\` on their own laptop.
2. A shared broker (anyone runs \`orchestra broker --tunnel\` once) routes JSON messages between agents.
3. When you ask a teammate, their agent spawns a Claude Agent SDK \`query()\` in their repo. CLAUDE.md, project skills, \`.mcp.json\` servers — all loaded automatically.
4. The browser UI you're looking at is just another peer of the agents. Same wire protocol.

## How to use this room

- **Online teammates** appear as desktop icons on the left edge.
- **Double-click an icon** to open the chat (works after you closed it with the red X too).
- **Type a question**, hit Enter — typical reply is 5–20 seconds.
- **File paths in answers are clickable** — click to copy the path to your clipboard.
- **Window chrome**: \`_\` minimize, \`□\` maximize (or double-click title bar), \`×\` close.
- **Drag** the title bar to move. **Resize** any edge. Positions auto-save.
- The blurred title bars mark unfocused windows — click one to bring it forward.

## Bring a teammate in

Share two things: **the broker URL** (printed when you ran \`orchestra broker --tunnel\`) and **the team code**. They install once:

\`\`\`
pip install --editable <orchestra-poc>     # or uv pip install -e ...
brew install cloudflared                    # only if they'll also host a broker
\`\`\`

Then they join:

\`\`\`
orchestra agent \\
  --team    <team-code> \\
  --as      <their-name> \\
  --broker  wss://...trycloudflare.com/ \\
  --repo    ~/code/their-microservice
\`\`\`

Their icon and chat window appear here automatically — no refresh needed.

## What this isn't (yet)

- **Browsers can't be asked** — this tab can ask others but it has no repo of its own, so asks to it just sit. The 60-second timeout will catch it.
- **No auth** — anyone with the broker URL + team code can join. Treat both as a shared secret. GitHub-OAuth gating is on the backlog.
- **No memory across asks** — each question gets a fresh Claude. Conversations don't persist on the answering side.

— *Orchestra v0.2  ·  Windows XP forever*
`;

export default function ReadmeWindow({ open, focused, onFocus, onClose, zIndex }) {
  const [{ pos, size }, setGeom] = useState(loadGeom);
  const logRef = useRef(null);

  useEffect(() => {
    saveGeom({ pos, size });
  }, [pos, size]);

  if (!open) return null;

  return (
    <Rnd
      className={`xp-window readme-window ${focused ? "focused" : "blurred"}`}
      style={{ zIndex }}
      position={pos}
      size={{ width: size.w, height: size.h }}
      bounds="parent"
      dragHandleClassName="title-bar"
      minWidth={420}
      minHeight={280}
      onMouseDown={onFocus}
      onDragStop={(_, d) => setGeom((g) => ({ ...g, pos: { x: d.x, y: d.y } }))}
      onResizeStop={(_, __, ref, ___, p) =>
        setGeom({ pos: { x: p.x, y: p.y }, size: { w: ref.offsetWidth, h: ref.offsetHeight } })
      }
    >
      <div className="title-bar">
        <div className="title-bar-text">
          <span className="title-bar-glyph" aria-hidden="true">i</span>
          Read Me — About Orchestra
        </div>
        <div className="title-bar-controls">
          <button aria-label="Minimize" disabled />
          <button aria-label="Maximize" disabled />
          <button aria-label="Close" onClick={onClose} />
        </div>
      </div>
      <div className="window-body readme-body" ref={logRef}>
        <ReactMarkdown>{README_MD}</ReactMarkdown>
      </div>
    </Rnd>
  );
}
