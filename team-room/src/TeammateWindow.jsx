import { useEffect, useRef, useState } from "react";
import { Rnd } from "react-rnd";
import ReactMarkdown from "react-markdown";
import { markdownComponents } from "./linkify.jsx";

const STATUS_TOOLTIPS = {
  online: "Online — answers from live repo",
  busy: "Composing answer…",
  stale: "Offline — last summary card available",
  error: "Connection error",
  offline: "Offline",
};

export default function TeammateWindow({
  teammate,
  messages,
  busy,
  status,
  state,
  focused,
  desktopRef,
  onAsk,
  onFocus,
  onMinimize,
  onMaximize,
  onClose,
  onGeometryChange,
  zIndex,
}) {
  const [draft, setDraft] = useState("");
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages?.length, busy]);

  const submit = (e) => {
    e.preventDefault();
    const q = draft.trim();
    if (!q || busy) return;
    onAsk(teammate, q);
    setDraft("");
  };

  if (!state.open || state.minimized) return null;

  // Compute Rnd controlled props. When maximized, fill the desktop.
  const desk = desktopRef?.current;
  const maxW = desk ? desk.clientWidth : 1280;
  const maxH = desk ? desk.clientHeight : 700;
  const position = state.maximized ? { x: 0, y: 0 } : state.pos;
  const size = state.maximized
    ? { width: maxW, height: maxH }
    : { width: state.size.w, height: state.size.h };

  const effectiveStatus = busy ? "busy" : status || "online";

  return (
    <Rnd
      className={`xp-window ${focused ? "focused" : "blurred"}`}
      style={{ zIndex }}
      position={position}
      size={size}
      bounds="parent"
      dragHandleClassName="title-bar"
      disableDragging={state.maximized}
      enableResizing={!state.maximized}
      minWidth={340}
      minHeight={240}
      onMouseDown={() => onFocus(teammate)}
      onDragStop={(_, d) => onGeometryChange(teammate, { pos: { x: d.x, y: d.y } })}
      onResizeStop={(_, __, ref, ___, pos) =>
        onGeometryChange(teammate, {
          pos: { x: pos.x, y: pos.y },
          size: { w: ref.offsetWidth, h: ref.offsetHeight },
        })
      }
    >
      <div className="title-bar" onDoubleClick={() => onMaximize(teammate)}>
        <div className="title-bar-text">
          <span
            className={`status-dot ${effectiveStatus}`}
            title={STATUS_TOOLTIPS[effectiveStatus] || effectiveStatus}
          />
          {teammate}
          {busy ? " — thinking…" : ""}
        </div>
        <div className="title-bar-controls">
          <button aria-label="Minimize" onClick={() => onMinimize(teammate)} />
          <button aria-label="Maximize" onClick={() => onMaximize(teammate)} />
          <button aria-label="Close" onClick={() => onClose(teammate)} />
        </div>
      </div>
      <div className="window-body">
        <div className="chat-log" ref={logRef}>
          {(!messages || messages.length === 0) && (
            <div className="chat-msg system">
              Ask {teammate}'s Claude anything about their repo. Replies typically take 5–20s.
            </div>
          )}
          {messages?.map((m) => (
            <div key={m.id} className={`chat-msg ${m.kind}`}>
              {m.who && <div className="who">{m.who}</div>}
              {m.kind === "them" ? (
                <ReactMarkdown components={markdownComponents}>{m.text}</ReactMarkdown>
              ) : (
                <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
              )}
            </div>
          ))}
          {busy && (
            <div className="chat-msg system busy-skeleton" aria-label="loading">
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
              <div className="skeleton-line" />
            </div>
          )}
        </div>
        <form className="chat-input-row" onSubmit={submit}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Ask ${teammate}…`}
            disabled={busy}
            autoFocus={focused}
          />
          <button type="submit" disabled={busy || !draft.trim()}>
            Send
          </button>
        </form>
      </div>
    </Rnd>
  );
}
