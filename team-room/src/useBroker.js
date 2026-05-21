/**
 * useBroker — single source of truth for the team-room's WebSocket connection
 * to the orchestra broker.
 *
 * Connects on mount, sends `hello`, then tracks:
 *   • current team members (from broker hello-ack and inferred via traffic)
 *   • per-teammate conversation logs
 *   • per-teammate "busy" state while an ask is outstanding
 *
 * Exposes one action: `ask(toName, question)` which sends a JSON `ask` to the
 * broker and returns immediately. The promise model isn't needed because
 * answers stream in via the websocket and update the conversation state.
 */

import { useEffect, useRef, useState, useCallback } from "react";

const uuid = () => crypto.randomUUID().replace(/-/g, "");
const ASK_TIMEOUT_MS = 60_000; // teammate has 60s to answer before we surface an error

export function useBroker({ team, display, brokerUrl }) {
  const [status, setStatus] = useState("connecting"); // connecting | open | closed | error
  const [members, setMembers] = useState([]); // string[]
  const [conversations, setConversations] = useState({}); // { [teammate]: msg[] }
  const [busy, setBusy] = useState({}); // { [teammate]: bool }
  
  const wsRef = useRef(null);
  const pendingRef = useRef({}); // { convId: { teammate, timeoutId } }
  const prevMembersRef = useRef([]); // Track previous members for change detection
  
  // Callbacks for member events - exposed for parent to subscribe to
  const onMemberJoinRef = useRef(null);
  const onMemberLeaveRef = useRef(null);
  
  const setMemberCallbacks = useCallback((onJoin, onLeave) => {
    onMemberJoinRef.current = onJoin;
    onMemberLeaveRef.current = onLeave;
  }, []);
  
  const log = useCallback((teammate, msg) => {
    setConversations((prev) => ({
      ...prev,
      [teammate]: [...(prev[teammate] || []), { id: uuid(), ts: Date.now(), ...msg }],
    }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const ws = new WebSocket(brokerUrl);
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      if (cancelled) return;
      ws.send(JSON.stringify({ type: "hello", team, display }));
      setStatus("open");
    });

    ws.addEventListener("message", (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      switch (msg.type) {
        case "hello-ack": {
          const newMembers = (msg.members || []).filter((m) => m !== display);
          const oldMembers = prevMembersRef.current;
          
          // Detect new members (joined)
          newMembers.forEach(m => {
            if (!oldMembers.includes(m) && onMemberJoinRef.current) {
              onMemberJoinRef.current(m, team);
            }
          });
          
          // Detect departed members (left)
          oldMembers.forEach(m => {
            if (!newMembers.includes(m) && onMemberLeaveRef.current) {
              onMemberLeaveRef.current(m);
            }
          });
          
          prevMembersRef.current = newMembers;
          setMembers(newMembers);
          break;
        }
        case "ask":
          // Someone asked us — we don't implement callee in the UI yet
          log(msg.from, { kind: "system", text: `${msg.from} asked you: "${msg.q}" — the team-room UI doesn't answer asks yet.` });
          break;
        case "answer": {
          const pending = pendingRef.current[msg.convId];
          const teammate = pending?.teammate || msg.from;
          if (pending?.timeoutId) clearTimeout(pending.timeoutId);
          delete pendingRef.current[msg.convId];
          setBusy((b) => ({ ...b, [teammate]: false }));
          log(teammate, { kind: "them", who: teammate, text: msg.a });
          break;
        }
        case "error": {
          const pending = pendingRef.current[msg.convId];
          if (pending) {
            if (pending.timeoutId) clearTimeout(pending.timeoutId);
            delete pendingRef.current[msg.convId];
            setBusy((b) => ({ ...b, [pending.teammate]: false }));
            log(pending.teammate, { kind: "system", text: `error: ${msg.reason}` });
          }
          break;
        }
        default:
          break;
      }
    });

    ws.addEventListener("close", () => {
      if (cancelled) return;
      setStatus("closed");
    });

    ws.addEventListener("error", () => {
      if (cancelled) return;
      setStatus("error");
    });

    return () => {
      cancelled = true;
      // Clear any in-flight ask timeouts to avoid firing after unmount.
      Object.values(pendingRef.current).forEach((p) => {
        if (p?.timeoutId) clearTimeout(p.timeoutId);
      });
      pendingRef.current = {};
      try { ws.close(); } catch {}
    };
  }, [team, display, brokerUrl, log]);

  /** Send an ask. Adds a "me" message to the convo and marks teammate busy. */
  const ask = useCallback(
    (to, question) => {
      const convId = uuid();
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        log(to, { kind: "system", text: "not connected to broker" });
        return;
      }
      log(to, { kind: "me", who: display, text: question });
      setBusy((b) => ({ ...b, [to]: true }));
      const timeoutId = setTimeout(() => {
        // Still waiting after ASK_TIMEOUT_MS — give up and surface as error.
        if (!pendingRef.current[convId]) return;
        delete pendingRef.current[convId];
        setBusy((b) => ({ ...b, [to]: false }));
        log(to, {
          kind: "system",
          text: `no answer from ${to} after ${Math.round(ASK_TIMEOUT_MS / 1000)}s — they may be offline or running an older client that can't reply.`,
        });
      }, ASK_TIMEOUT_MS);
      pendingRef.current[convId] = { teammate: to, timeoutId };
      ws.send(
        JSON.stringify({
          type: "ask",
          from: display,
          to,
          q: question,
          convId,
        })
      );
    },
    [display, log]
  );

  return { status, members, conversations, busy, ask, setMemberCallbacks };
}
