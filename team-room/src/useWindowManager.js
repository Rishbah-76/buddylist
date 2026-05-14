/**
 * useWindowManager — per-teammate window state (position, size, mode) with
 * focus stack and localStorage persistence.
 *
 * State shape per teammate:
 *   { open: bool, minimized: bool, maximized: bool, pos: {x,y}, size: {w,h} }
 *
 * Plus a focus stack (array of names, frontmost is last) used for z-index.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_SIZE = { w: 460, h: 360 };
const CASCADE = { x: 110, y: 30, step: 34 };  // x clears the desktop-icons column on the left

function lsKey(team) {
  return `orchestra:window-state:${team}`;
}

function loadPersisted(team) {
  try {
    const raw = localStorage.getItem(lsKey(team));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePersisted(team, windows) {
  try {
    const slim = Object.fromEntries(
      Object.entries(windows).map(([name, w]) => [
        name,
        { pos: w.pos, size: w.size, open: w.open, minimized: w.minimized, maximized: w.maximized },
      ])
    );
    localStorage.setItem(lsKey(team), JSON.stringify(slim));
  } catch {
    /* quota or disabled — ignore */
  }
}

function makeDefault(idx) {
  return {
    open: true,
    minimized: false,
    maximized: false,
    pos: { x: CASCADE.x + idx * CASCADE.step, y: CASCADE.y + idx * CASCADE.step },
    size: { ...DEFAULT_SIZE },
  };
}

export function useWindowManager({ team, members }) {
  const [windows, setWindows] = useState(() => loadPersisted(team));
  const [focusStack, setFocusStack] = useState([]);
  const seenRef = useRef(new Set());

  // Ensure each member has a window record (default normal-state).
  useEffect(() => {
    setWindows((prev) => {
      let next = prev;
      let mutated = false;
      members.forEach((name, idx) => {
        if (!next[name]) {
          if (!mutated) {
            next = { ...prev };
            mutated = true;
          }
          next[name] = makeDefault(idx);
        }
      });
      return mutated ? next : prev;
    });
    // Track first-time appearance to seed focus stack
    setFocusStack((prev) => {
      let next = prev;
      members.forEach((name) => {
        if (!seenRef.current.has(name)) {
          seenRef.current.add(name);
          if (!next.includes(name)) next = [...next, name];
        }
      });
      return next === prev ? prev : next;
    });
  }, [members]);

  // Persist whenever windows change
  useEffect(() => {
    savePersisted(team, windows);
  }, [team, windows]);

  const focus = useCallback((name) => {
    setFocusStack((s) => (s[s.length - 1] === name ? s : [...s.filter((n) => n !== name), name]));
  }, []);

  const setWin = useCallback((name, patch) => {
    setWindows((prev) => {
      const cur = prev[name] || makeDefault(0);
      const merged = { ...cur, ...patch };
      // Cheap shallow-equality guard
      if (
        merged.open === cur.open &&
        merged.minimized === cur.minimized &&
        merged.maximized === cur.maximized &&
        merged.pos?.x === cur.pos?.x &&
        merged.pos?.y === cur.pos?.y &&
        merged.size?.w === cur.size?.w &&
        merged.size?.h === cur.size?.h
      ) {
        return prev;
      }
      return { ...prev, [name]: merged };
    });
  }, []);

  const minimize = useCallback((name) => setWin(name, { minimized: true }), [setWin]);
  const maximize = useCallback(
    (name) => {
      setWindows((prev) => {
        const cur = prev[name] || makeDefault(0);
        return { ...prev, [name]: { ...cur, maximized: !cur.maximized, minimized: false } };
      });
      focus(name);
    },
    [focus]
  );
  const close = useCallback((name) => setWin(name, { open: false, minimized: false }), [setWin]);
  const open = useCallback(
    (name) => {
      setWin(name, { open: true, minimized: false });
      focus(name);
    },
    [setWin, focus]
  );

  /** Called by useBroker when a new answer arrives for a teammate — reopen if closed. */
  const ensureVisible = useCallback(
    (name) => {
      setWin(name, { open: true, minimized: false });
      focus(name);
    },
    [setWin, focus]
  );

  const updateGeometry = useCallback(
    (name, { pos, size }) => {
      const patch = {};
      if (pos) patch.pos = pos;
      if (size) patch.size = size;
      setWin(name, patch);
    },
    [setWin]
  );

  const zIndexFor = useCallback(
    (name) => {
      const i = focusStack.indexOf(name);
      return 20 + (i < 0 ? 0 : i);
    },
    [focusStack]
  );

  const focused = focusStack[focusStack.length - 1] || null;

  return {
    windows,
    focused,
    focus,
    minimize,
    maximize,
    close,
    open,
    ensureVisible,
    updateGeometry,
    zIndexFor,
  };
}
