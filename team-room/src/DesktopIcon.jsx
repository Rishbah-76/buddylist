/**
 * DesktopIcon — one XP-style desktop shortcut per online teammate.
 * Single-click selects (blue tint). Double-click (or Enter when focused) opens
 * the teammate's chat window — used to recover a window after the user closed
 * it with the title-bar X.
 */

import { useId } from "react";

function BuddyGlyph() {
  // Stable IDs per instance so gradients don't collide across icons.
  const uid = useId().replace(/:/g, "");
  const head = `head-${uid}`;
  const body = `body-${uid}`;
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id={head} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffe1bd" />
          <stop offset="100%" stopColor="#deaa78" />
        </linearGradient>
        <linearGradient id={body} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7eb1ff" />
          <stop offset="100%" stopColor="#3a6ec5" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="10" r="6" fill={`url(#${head})`} stroke="#7a5028" strokeWidth="0.5" />
      <path
        d="M 4 32 Q 4 22 16 22 Q 28 22 28 32 Z"
        fill={`url(#${body})`}
        stroke="#1c4488"
        strokeWidth="0.5"
      />
    </svg>
  );
}

export function DocumentGlyph() {
  const uid = useId().replace(/:/g, "");
  const bg = `doc-${uid}`;
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id={bg} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#d8d8d8" />
        </linearGradient>
      </defs>
      <path
        d="M 6 2 L 22 2 L 28 8 L 28 30 L 6 30 Z"
        fill={`url(#${bg})`}
        stroke="#7a7a7a"
        strokeWidth="0.8"
      />
      <path d="M 22 2 L 22 8 L 28 8 Z" fill="#bcbcbc" stroke="#7a7a7a" strokeWidth="0.6" />
      <line x1="10" y1="14" x2="24" y2="14" stroke="#7a7a7a" strokeWidth="0.7" />
      <line x1="10" y1="18" x2="24" y2="18" stroke="#7a7a7a" strokeWidth="0.7" />
      <line x1="10" y1="22" x2="20" y2="22" stroke="#7a7a7a" strokeWidth="0.7" />
    </svg>
  );
}

export default function DesktopIcon({
  name,
  label,
  glyph,
  status,
  isOpen,
  selected,
  onSelect,
  onOpen,
  ariaLabel,
}) {
  const Glyph = glyph || BuddyGlyph;
  const labelText = label ?? name;
  return (
    <div
      className={`desktop-icon ${selected ? "selected" : ""} ${isOpen ? "is-open" : "is-closed"}`}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(name);
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        onOpen(name);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(name);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={ariaLabel || `Open ${labelText}`}
      title={`Double-click to open ${labelText}`}
    >
      <div className="icon-graphic">
        <Glyph />
        {status && <span className={`status-dot ${status}`} title={status} />}
      </div>
      <div className="icon-label">{labelText}</div>
    </div>
  );
}
