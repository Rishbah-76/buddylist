import { useEffect, useMemo, useRef, useState } from "react";
import TeammateWindow from "./TeammateWindow.jsx";
import DesktopIcon, { DocumentGlyph } from "./DesktopIcon.jsx";
import ReadmeWindow from "./ReadmeWindow.jsx";
import StartMenu from "./StartMenu.jsx";
import NotificationBalloon, { useNotifications } from "./NotificationBalloon.jsx";
import { useBroker } from "./useBroker.js";
import { useWindowManager } from "./useWindowManager.js";

const README_SEEN_KEY = "orchestra:readme:seen";

function readUrlParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    team: p.get("team") || "spike04-test",
    display: p.get("name") || "guest-ui",
    brokerUrl: p.get("broker") || "ws://localhost:8765/",
  };
}

export default function App() {
  const cfg = useMemo(readUrlParams, []);
  const broker = useBroker(cfg);
  const { status, members, conversations, busy, ask, setMemberCallbacks } = broker;
  const desktopRef = useRef(null);
  const wm = useWindowManager({ team: cfg.team, members });
  const lastAnswerCountRef = useRef({});
  const [selectedIcon, setSelectedIcon] = useState(null);
  const [readmeOpen, setReadmeOpen] = useState(() => {
    try { return !localStorage.getItem(README_SEEN_KEY); } catch { return true; }
  });
  const [startMenuOpen, setStartMenuOpen] = useState(false);
  const [topmost, setTopmost] = useState(readmeOpen ? "__readme" : null);
  
  // Notifications
  const { notifications, notifyTeammateOnline, notifyTeammateOffline } = useNotifications();
  
  // Wire broker to trigger notifications on member join/leave
  useEffect(() => {
    setMemberCallbacks(
      (name, team) => notifyTeammateOnline(name, team),
      (name) => notifyTeammateOffline(name)
    );
  }, [setMemberCallbacks, notifyTeammateOnline, notifyTeammateOffline]);

  // Auto-reopen a closed teammate window when a new answer arrives.
  useEffect(() => {
    Object.entries(conversations).forEach(([teammate, msgs]) => {
      const prevCount = lastAnswerCountRef.current[teammate] || 0;
      if (msgs.length > prevCount) {
        const newest = msgs[msgs.length - 1];
        if (newest.kind === "them") {
          wm.ensureVisible(teammate);
          setTopmost(teammate);
        }
      }
      lastAnswerCountRef.current[teammate] = msgs.length;
    });
  }, [conversations, wm]);

  const handlePillClick = (name) => {
    const win = wm.windows[name];
    if (!win || !win.open) return wm.open(name);
    if (win.minimized) {
      wm.open(name);
      setTopmost(name);
      return;
    }
    if (wm.focused === name && topmost === name) {
      wm.minimize(name);
    } else {
      wm.focus(name);
      setTopmost(name);
    }
  };

  const focusTeammate = (name) => {
    wm.focus(name);
    setTopmost(name);
  };

  const openTeammate = (name) => {
    wm.open(name);
    setTopmost(name);
  };

  const closeReadme = () => {
    setReadmeOpen(false);
    try { localStorage.setItem(README_SEEN_KEY, "1"); } catch {}
  };

  const openReadme = () => {
    setReadmeOpen(true);
    setTopmost("__readme");
  };

  const focusReadme = () => setTopmost("__readme");

  const readmeZ = topmost === "__readme" ? 100 : 15;

  return (
    <>
      <div className="desktop" ref={desktopRef} onClick={() => setSelectedIcon(null)}>
        <div className="desktop-icons">
          <DesktopIcon
            name="__readme"
            label="Read Me"
            glyph={DocumentGlyph}
            isOpen={readmeOpen}
            selected={selectedIcon === "__readme"}
            onSelect={setSelectedIcon}
            onOpen={openReadme}
            ariaLabel="Open the Read Me / About Orchestra window"
          />
          {members.map((name) => {
            const w = wm.windows[name];
            const isOpen = !!w?.open && !w?.minimized;
            return (
              <DesktopIcon
                key={name}
                name={name}
                status={busy[name] ? "busy" : "online"}
                isOpen={isOpen}
                selected={selectedIcon === name}
                onSelect={setSelectedIcon}
                onOpen={openTeammate}
              />
            );
          })}
        </div>

        {members.length === 0 && !readmeOpen && (
          <div className="desktop-hint">
            {status === "connecting" && <>Connecting to broker at <code>{cfg.brokerUrl}</code>…</>}
            {status === "open" && <>No teammates connected yet. Start an orchestra-agent to join the team <b>{cfg.team}</b>.</>}
            {status === "closed" && <>Disconnected from broker. Refresh to reconnect.</>}
            {status === "error" && <>Couldn't reach broker at <code>{cfg.brokerUrl}</code>. Is it running?</>}
          </div>
        )}

        <ReadmeWindow
          open={readmeOpen}
          focused={topmost === "__readme"}
          onFocus={focusReadme}
          onClose={closeReadme}
          zIndex={readmeZ}
        />

        {members.map((teammate) => {
          const ws = wm.windows[teammate];
          if (!ws) return null;
          return (
            <TeammateWindow
              key={teammate}
              teammate={teammate}
              messages={conversations[teammate]}
              busy={!!busy[teammate]}
              status="online"
              state={ws}
              focused={wm.focused === teammate && topmost === teammate}
              desktopRef={desktopRef}
              onAsk={ask}
              onFocus={focusTeammate}
              onMinimize={wm.minimize}
              onMaximize={wm.maximize}
              onClose={wm.close}
              onGeometryChange={wm.updateGeometry}
              zIndex={wm.zIndexFor(teammate)}
            />
          );
        })}
      </div>
      <div className="taskbar">
        <button 
          className="start-button" 
          type="button"
          onClick={() => setStartMenuOpen(!startMenuOpen)}
          title="Start"
        >start</button>
        <div className="taskbar-windows">
          {readmeOpen && (
            <button
              type="button"
              className={`taskbar-pill ${topmost === "__readme" ? "active" : ""}`}
              onClick={focusReadme}
              title="Read Me"
            >
              <span className="pill-glyph" aria-hidden="true">i</span>
              Read Me
            </button>
          )}
          {members.map((name) => {
            const ws = wm.windows[name];
            if (!ws || !ws.open) return null;
            const active = wm.focused === name && topmost === name && !ws.minimized;
            return (
              <button
                key={name}
                type="button"
                className={`taskbar-pill ${active ? "active" : ""} ${ws.minimized ? "minimized" : ""}`}
                onClick={() => handlePillClick(name)}
                title={name}
              >
                <span className={`status-dot online`} />
                {name}
              </button>
            );
          })}
        </div>
        <div className="taskbar-tray">
          <span className="tray-info">team: <b>{cfg.team}</b> · you: <b>{cfg.display}</b></span>
          <span className={`tray-status status-${status}`} title={`broker: ${status}`}>{status}</span>
        </div>
      </div>
      
      {/* Start Menu Popup */}
      <StartMenu 
        isOpen={startMenuOpen}
        onClose={() => setStartMenuOpen(false)}
        currentTeam={cfg.team}
        availableTeams={[cfg.team]}
        displayName={cfg.display}
        onTeamChange={(team) => {
          // TODO: Trigger reconnection with new team
          console.log('Switch to team:', team);
        }}
      />
      
      {/* Notification Balloons */}
      <NotificationBalloon notifications={notifications} />
    </>
  );
}
